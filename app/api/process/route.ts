import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { getUserProjects, createMap } from '@/lib/firebase-admin'
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
        const mapData = await createMap(userId, projectId, {
            name: `${parameter} Map`,
            parameter,
            colormap,
            dataPoints: processedData.length,
            statistics: { min, max, avg },
            status: 'completed'
        })

        return NextResponse.json({
            success: true,
            mapId: mapData.id,
            data: processedData,
            statistics: { min, max, avg },
            colorScale,
            contourData,
            bounds: calculateBounds(processedData)
        })
    } catch (error: any) {
        console.error('Error processing map:', error)
        return NextResponse.json({ error: error.message || 'Failed to process map' }, { status: 500 })
    }
}

function generateColorScale(colormap: string, min: number, max: number) {
    // Color scales for different colormaps
    const scales: Record<string, string[]> = {
        viridis: ['#440154', '#482878', '#3e4a89', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6dcd59', '#b4de2c', '#fde725'],
        blues: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b'],
        greens: ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#006d2c', '#00441b'],
        reds: ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#a50f15', '#67000d']
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
