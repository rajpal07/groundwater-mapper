import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { getUserProjects, createMap, updateMap } from '@/lib/firebase-admin'
import * as XLSX from 'xlsx'

export const dynamic = 'force-dynamic'

export async function POST(request: Request): Promise<NextResponse> {
    try {
        const session = await getServerSession(authOptions)
        const userId = session?.user?.email

        if (!userId) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const formData = await request.formData()
        const file = formData.get('file') as File
        const parameter = formData.get('parameter') as string
        const colormap = formData.get('colormap') as string || 'viridis'
        const projectId = formData.get('projectId') as string
        const mapId = formData.get('mapId') as string
        const useAIProcessing = formData.get('useAIProcessing') === 'true'

        if (!file || !parameter || !projectId) {
            return NextResponse.json({ error: 'Missing required fields' }, { status: 400 })
        }

        // Verify project belongs to user
        const projects = await getUserProjects(userId)
        const project = projects.find(p => p.id === projectId)

        if (!project) {
            return NextResponse.json({ error: 'Project not found' }, { status: 404 })
        }

        // Read and process Excel file
        const buffer = Buffer.from(await file.arrayBuffer())
        const workbook = XLSX.read(buffer, { type: 'buffer' })
        const sheetName = workbook.SheetNames[0]
        const worksheet = workbook.Sheets[sheetName]
        const data = XLSX.utils.sheet_to_json(worksheet)

        if (!data || data.length === 0) {
            return NextResponse.json({ error: 'No data found in Excel file' }, { status: 400 })
        }

        // Get all columns from the first row to identify numeric columns
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
            value: parseFloat(row[parameter] || row.Value || row.value || 0)
        })).filter(point =>
            !isNaN(point.lat) && !isNaN(point.lon) && !isNaN(point.value)
        )

        if (processedData.length === 0) {
            return NextResponse.json({
                error: `No valid data found for parameter "${parameter}". Please check your Excel file.`
            }, { status: 400 })
        }

        // Calculate statistics
        const values = processedData.map(p => p.value)
        const min = Math.min(...values)
        const max = Math.max(...values)
        const avg = values.reduce((a, b) => a + b, 0) / values.length

        // Generate color scale based on colormap
        const colorScale = generateColorScale(colormap, min, max)

        // Create contour data (simplified interpolation)
        const contourData = generateContourData(processedData, min, max)

        // Save map to Firebase
        const mapData = await updateMap(userId, projectId, mapId, {
            parameter,
            colormap,
            dataPoints: processedData.length,
            statistics: { min, max, avg },
            status: 'complete',
            processedAt: new Date().toISOString()
        })

        return NextResponse.json({
            success: true,
            mapId: mapId,
            data: processedData,
            statistics: { min, max, avg },
            colorScale,
            contourData,
            bounds: calculateBounds(processedData),
            availableParameters: numericColumns
        })
    } catch (error: any) {
        console.error('Error processing map:', error)
        return NextResponse.json({ error: error.message || 'Failed to process map' }, { status: 500 })
    }
}

function generateColorScale(colormap: string, min: number, max: number) {
    // Color scales for different colormaps - matching Streamlit app options
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
        BuPu: ['#f7fcfd', '#e0f3f8', '#bdc9e1', '#74a9cf', '#2b8cbe', '#045a8d', '#023858'],
        GnBu: ['#f7fcf0', '#e0f3db', '#c7e9c0', '#a1d99b', '#7bccc4', '#4eb3d3', '#2b8cbe', '#0868a9', '#084081'],
        OrRd: ['#fff7ec', '#fee8c8', '#fdd49e', '#fdbb84', '#fc8d59', '#ef6548', '#d7301f', '#b30000', '#7f0000'],
        PuBu: ['#fff7fb', '#ece7f2', '#d0d1e6', '#a6bddb', '#74a9cf', '#3690c0', '#0570b0', '#045a8d', '#023858'],
        PuRd: ['#f7f4f9', '#e7e1ef', '#d4b9da', '#c994c7', '#df65b0', '#e7298a', '#ce1256', '#980043', '#67001f'],
        BrBG: ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e', '#003c30'],
        PRGn: ['#7f3bb7', '#af8dc3', '#e7d4e8', '#d9f0d3', '#7fbf7b', '#1d9661', '#00441b'],
        PiYG: ['#c51b8a', '#fde0dd', '#fbb4ae', '#f768a1', '#e78f8e', '#eb9ca3', '#d01c8b', '#b8e186', '#7fbc41', '#4d9221']
    }

    const colors = scales[colormap] || scales.viridis
    const step = (max - min) / (colors.length - 1)

    return colors.map((color, i) => ({
        color,
        value: min + (i * step)
    }))
}

function generateContourData(data: { lat: number; lon: number; value: number }[], min: number, max: number) {
    // Simplified contour generation - create contour levels
    const numLevels = 10
    const step = (max - min) / numLevels

    const contours = []
    for (let i = 0; i < numLevels; i++) {
        const level = min + (i * step)
        contours.push({
            level,
            points: data.filter(d => Math.abs(d.value - level) < step / 2)
        })
    }

    return contours
}

function calculateBounds(data: { lat: number; lon: number }[]) {
    const lats = data.map(d => d.lat)
    const lons = data.map(d => d.lon)

    return {
        north: Math.max(...lats),
        south: Math.min(...lats),
        east: Math.max(...lons),
        west: Math.min(...lons)
    }
}
