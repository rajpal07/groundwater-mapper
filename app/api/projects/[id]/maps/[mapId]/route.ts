import { NextRequest, NextResponse } from 'next/server'
import { verifyFirebaseToken, getMap } from '@/lib/firebase-admin'

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string; mapId: string }> }
) {
    try {
        const resolvedParams = await params
        const authHeader = request.headers.get('Authorization')

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const token = authHeader.split('Bearer ')[1]
        const user = await verifyFirebaseToken(token)

        if (!user) {
            return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
        }

        const map = await getMap(user.uid, resolvedParams.id, resolvedParams.mapId)

        if (!map) {
            return NextResponse.json({ error: 'Map not found' }, { status: 404 })
        }

        return NextResponse.json({ map })
    } catch (error) {
        console.error('Error fetching map:', error)
        return NextResponse.json({ error: 'Failed to fetch map' }, { status: 500 })
    }
}

export async function DELETE(
    request: NextRequest,
    { params }: { params: Promise<{ id: string; mapId: string }> }
) {
    try {
        const resolvedParams = await params
        const authHeader = request.headers.get('Authorization')

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const token = authHeader.split('Bearer ')[1]
        const user = await verifyFirebaseToken(token)

        if (!user) {
            return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
        }

        // Delete the map
        const { deleteMap } = await import('@/lib/firebase-admin')
        await deleteMap(user.uid, resolvedParams.id, resolvedParams.mapId)

        return NextResponse.json({ success: true })
    } catch (error) {
        console.error('Error deleting map:', error)
        return NextResponse.json({ error: 'Failed to delete map' }, { status: 500 })
    }
}
