import { NextResponse } from 'next/server'
import { verifyIdToken, getProjectMaps, createMap, deleteMap, getProject, getMap } from '@/lib/firebase-admin'

export const dynamic = 'force-dynamic'

// Get maps for a project
export async function GET(request: Request) {
    try {
        const authHeader = request.headers.get('authorization')
        if (!authHeader?.startsWith('Bearer ')) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const idToken = authHeader.split('Bearer ')[1]
        const decodedToken = await verifyIdToken(idToken)

        if (!decodedToken) {
            return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
        }

        const userId = decodedToken.uid
        const { searchParams } = new URL(request.url)
        const projectId = searchParams.get('projectId')
        const mapId = searchParams.get('mapId')

        if (!projectId) {
            return NextResponse.json({ error: 'Project ID required' }, { status: 400 })
        }

        // Verify project exists
        const project = await getProject(userId, projectId)
        if (!project) {
            return NextResponse.json({ error: 'Project not found' }, { status: 404 })
        }

        if (mapId) {
            const map = await getMap(userId, projectId, mapId)
            if (!map) {
                return NextResponse.json({ error: 'Map not found' }, { status: 404 })
            }
            return NextResponse.json(map)
        }

        const maps = await getProjectMaps(userId, projectId)
        return NextResponse.json(maps)
    } catch (error) {
        console.error('Error fetching maps:', error)
        return NextResponse.json({ error: 'Failed to fetch maps' }, { status: 500 })
    }
}

// Create a new map
export async function POST(request: Request) {
    try {
        const authHeader = request.headers.get('authorization')
        if (!authHeader?.startsWith('Bearer ')) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const idToken = authHeader.split('Bearer ')[1]
        const decodedToken = await verifyIdToken(idToken)

        if (!decodedToken) {
            return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
        }

        const userId = decodedToken.uid
        const body = await request.json()
        const { projectId, name, parameter, colormap, excelData, processedData, mapHtml, bounds, targetPoints } = body

        if (!projectId || !name) {
            return NextResponse.json({ error: 'Project ID and name required' }, { status: 400 })
        }

        // Verify project exists
        const project = await getProject(userId, projectId)
        if (!project) {
            return NextResponse.json({ error: 'Project not found' }, { status: 404 })
        }

        const map = await createMap(userId, projectId, {
            name,
            parameter,
            colormap,
            excelData,
            processedData,
            mapHtml,
            bounds,
            targetPoints
        })

        return NextResponse.json(map)
    } catch (error) {
        console.error('Error creating map:', error)
        return NextResponse.json({ error: 'Failed to create map' }, { status: 500 })
    }
}

// Delete a map
export async function DELETE(request: Request) {
    try {
        const authHeader = request.headers.get('authorization')
        if (!authHeader?.startsWith('Bearer ')) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const idToken = authHeader.split('Bearer ')[1]
        const decodedToken = await verifyIdToken(idToken)

        if (!decodedToken) {
            return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
        }

        const userId = decodedToken.uid
        const { searchParams } = new URL(request.url)
        const projectId = searchParams.get('projectId')
        const mapId = searchParams.get('id')

        if (!projectId || !mapId) {
            return NextResponse.json({ error: 'Project ID and Map ID required' }, { status: 400 })
        }

        await deleteMap(userId, projectId, mapId)
        return NextResponse.json({ success: true })
    } catch (error) {
        console.error('Error deleting map:', error)
        return NextResponse.json({ error: 'Failed to delete map' }, { status: 500 })
    }
}
