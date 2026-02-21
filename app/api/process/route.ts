import { NextResponse } from 'next/server'
import { verifyIdToken, getUserProjects, updateMap } from '@/lib/firebase-admin'
import { processExcelFromBuffer, isPythonServiceConfigured, exceedsVercelLimit, PythonApiError } from '@/lib/python-api'
import * as XLSX from 'xlsx'

export const dynamic = 'force-dynamic'

/**
 * Helper function to verify Firebase ID token from Authorization header
 */
async function getAuthenticatedUserId(request: Request): Promise<string | null> {
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        console.log('[Process API] No Bearer token in Authorization header')
        return null
    }

    const idToken = authHeader.substring(7) // Remove 'Bearer ' prefix
    console.log('[Process API] Verifying ID token...')

    const decodedToken = await verifyIdToken(idToken)
    if (!decodedToken) {
        console.log('[Process API] Token verification failed')
        return null
    }

    console.log('[Process API] Token verified for user:', decodedToken.uid)
    return decodedToken.uid
}

/**
 * POST /api/process
 * Process an Excel file and generate contour map data
 * 
 * This route proxies to the Python FastAPI service for heavy processing,
 * with a Node.js fallback for small files or when Python service is unavailable.
 */
export async function POST(request: Request): Promise<NextResponse> {
    console.log('[Process API] Request received')

    try {
        // 1. Authenticate user
        const userId = await getAuthenticatedUserId(request)
        if (!userId) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        // 2. Parse form data
        const formData = await request.formData()
        const file = formData.get('file') as File
        const parameter = formData.get('parameter') as string
        const colormap = (formData.get('colormap') as string) || 'viridis'
        const projectId = formData.get('projectId') as string
        const mapId = formData.get('mapId') as string
        const sheetName = formData.get('sheet_name') as string | null
        const interpolationMethod = (formData.get('interpolation_method') as string) || 'linear'

        console.log('[Process API] File:', file?.name, 'size:', file?.size)
        console.log('[Process API] Parameter:', parameter, 'Project:', projectId, 'Map:', mapId)

        // 3. Validate required fields
        if (!file || !parameter || !projectId) {
            return NextResponse.json({ error: 'Missing required fields: file, parameter, projectId' }, { status: 400 })
        }

        // 4. Verify project belongs to user
        const projects = await getUserProjects(userId)
        const project = projects.find(p => p.id === projectId)
        if (!project) {
            console.log('[Process API] Project not found:', projectId)
            return NextResponse.json({ error: 'Project not found' }, { status: 404 })
        }

        // 5. Get auth token for Python API
        const authHeader = request.headers.get('Authorization')
        const token = authHeader?.substring(7) || ''

        // 6. Convert file to buffer
        const buffer = Buffer.from(await file.arrayBuffer())

        // 7. Try Python FastAPI service first (if configured and file is large enough)
        if (isPythonServiceConfigured()) {
            console.log('[Process API] Python service configured, attempting to use it')

            try {
                const result = await processExcelFromBuffer(buffer, file.name, parameter, token, {
                    colormap,
                    interpolation_method: interpolationMethod as 'linear' | 'cubic' | 'nearest',
                    sheet_name: sheetName || undefined,
                })

                console.log('[Process API] Python service success, processed data with', result.statistics.count, 'points')

                // Save map metadata to Firebase
                await updateMap(userId, projectId, mapId, {
                    parameter,
                    colormap,
                    dataPoints: result.statistics.count,
                    statistics: {
                        min: result.statistics.min,
                        max: result.statistics.max,
                        avg: result.statistics.mean,
                        std: result.statistics.std,
                    },
                    coordinateSystem: result.coordinate_system,
                    status: 'complete',
                    processedAt: new Date().toISOString(),
                    parseMethod: result.parse_method,
                })

                return NextResponse.json({
                    success: true,
                    mapId,
                    mapHtml: result.map_html,
                    data: [], // Data is embedded in map_html
                    statistics: {
                        min: result.statistics.min,
                        max: result.statistics.max,
                        avg: result.statistics.mean,
                        std: result.statistics.std,
                        count: result.statistics.count,
                    },
                    colorScale: result.contour_data.colors.map((color, i) => ({
                        color,
                        value: result.contour_data.levels[i],
                    })),
                    contourData: result.contour_data,
                    bounds: result.bounds ? {
                        north: result.bounds.max_lat,
                        south: result.bounds.min_lat,
                        east: result.bounds.max_lon,
                        west: result.bounds.min_lon,
                    } : undefined,
                    coordinateSystem: result.coordinate_system,
                    source: 'python',
                })
            } catch (error) {
                if (error instanceof PythonApiError) {
                    console.error('[Process API] Python API error:', error.message, error.details)

                    // If it's a client error (4xx), return the error to the client
                    if (error.status >= 400 && error.status < 500) {
                        return NextResponse.json(
                            { error: error.message, details: error.details },
                            { status: error.status }
                        )
                    }
                } else {
                    console.error('[Process API] Python service error:', error)
                }
                // Fall through to Node.js fallback
            }
        } else {
            console.log('[Process API] Python service not configured, using Node.js fallback')
        }

        // 8. Node.js fallback implementation
        console.log('[Process API] Using Node.js fallback')
        return await processWithNodeJS(buffer, file.name, parameter, colormap, userId, projectId, mapId)
    } catch (error: any) {
        console.error('[Process API] Error:', error)
        return NextResponse.json(
            { error: error.message || 'Failed to process map' },
            { status: 500 }
        )
    }
}

/**
 * Node.js fallback implementation for processing Excel files
 * Used when Python service is unavailable or for small files
 */
async function processWithNodeJS(
    buffer: Buffer,
    filename: string,
    parameter: string,
    colormap: string,
    userId: string,
    projectId: string,
    mapId: string
): Promise<NextResponse> {
    // Read Excel file
    const workbook = XLSX.read(buffer, { type: 'buffer' })
    const sheetName = workbook.SheetNames[0]
    const worksheet = workbook.Sheets[sheetName]
    const data = XLSX.utils.sheet_to_json(worksheet)

    if (!data || data.length === 0) {
        return NextResponse.json({ error: 'No data found in Excel file' }, { status: 400 })
    }

    // Get numeric columns
    const firstRow = data[0] as Record<string, any>
    const allColumns = Object.keys(firstRow)
    const numericColumns = allColumns.filter(col => {
        const value = firstRow[col]
        return typeof value === 'number' || (!isNaN(parseFloat(value)) && isFinite(value))
    })

    // Process data - extract lat, lon, and parameter values
    const processedData = data.map((row: any) => ({
        lat: parseFloat(row.Latitude || row.lat || row.LAT || 0),
        lon: parseFloat(row.Longitude || row.lon || row.LON || row.Long || row.lng || 0),
        value: parseFloat(row[parameter] || row.Value || row.value || 0),
    })).filter(point => !isNaN(point.lat) && !isNaN(point.lon) && !isNaN(point.value))

    if (processedData.length === 0) {
        return NextResponse.json({
            error: `No valid data found for parameter "${parameter}". Please check your Excel file.`,
        }, { status: 400 })
    }

    // Calculate statistics
    const values = processedData.map(p => p.value)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const avg = values.reduce((a, b) => a + b, 0) / values.length

    // Generate color scale
    const colorScale = generateColorScale(colormap, min, max)

    // Create contour data (simplified)
    const contourData = generateContourData(processedData, min, max)

    // Calculate bounds
    const bounds = calculateBounds(processedData)

    // Save map to Firebase
    await updateMap(userId, projectId, mapId, {
        parameter,
        colormap,
        dataPoints: processedData.length,
        statistics: { min, max, avg },
        status: 'complete',
        processedAt: new Date().toISOString(),
    })

    console.log('[Process API] Node.js fallback success, processed', processedData.length, 'data points')

    return NextResponse.json({
        success: true,
        mapId,
        data: processedData,
        statistics: { min, max, avg, count: processedData.length },
        colorScale,
        contourData,
        bounds,
        availableParameters: numericColumns,
        source: 'nodejs',
    })
}

/**
 * Generate a color scale for the given colormap
 */
function generateColorScale(colormap: string, min: number, max: number) {
    const scales: Record<string, string[]> = {
        viridis: ['#440154', '#482878', '#3e4a89', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6dcd59', '#b4de2c', '#fde725'],
        plasma: ['#0d0887', '#46039f', '#7201a8', '#9c179e', '#bd3786', '#d8576b', '#ed7953', '#fb9f3a', '#fdca26', '#f0f921'],
        RdYlBu_r: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
        RdYlBu: ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee090', '#e0f3f8', '#abd9e9', '#74add1', '#4575b4', '#313695'],
        blues: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b'],
        greens: ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#006d2c', '#00441b'],
        reds: ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#a50f15', '#67000d'],
        YlOrRd: ['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026'],
        YlGn: ['#ffffe5', '#f7fcb9', '#addd8e', '#41ab5d', '#238b45', '#006d2c', '#00441b'],
        YlGnBu: ['#ffffd9', '#edf8b1', '#c7e9b4', '#7fcdbb', '#41b6c4', '#1d91c0', '#225ea8', '#253494', '#081d58'],
    }

    const colors = scales[colormap] || scales.viridis
    const step = (max - min) / (colors.length - 1)

    return colors.map((color, i) => ({
        color,
        value: min + i * step,
    }))
}

/**
 * Generate simplified contour data
 */
function generateContourData(data: { lat: number; lon: number; value: number }[], min: number, max: number) {
    const numLevels = 10
    const step = (max - min) / numLevels
    const contours = []

    for (let i = 0; i < numLevels; i++) {
        const level = min + i * step
        contours.push({
            level,
            points: data.filter(d => Math.abs(d.value - level) < step / 2),
        })
    }

    return contours
}

/**
 * Calculate bounds from data points
 */
function calculateBounds(data: { lat: number; lon: number }[]) {
    const lats = data.map(d => d.lat)
    const lons = data.map(d => d.lon)

    return {
        north: Math.max(...lats),
        south: Math.min(...lats),
        east: Math.max(...lons),
        west: Math.min(...lons),
    }
}
