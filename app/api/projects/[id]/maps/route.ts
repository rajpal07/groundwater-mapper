import { NextRequest, NextResponse } from 'next/server'
import { verifyFirebaseToken, createMap, getMap, getProjectMaps } from '@/lib/firebase-admin'

export async function POST(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
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

        const body = await request.json()
        const { name } = body

        if (!name) {
            return NextResponse.json({ error: 'Map name is required' }, { status: 400 })
        }

        const map = await createMap(user.uid, resolvedParams.id, { name })
        return NextResponse.json(map)
    } catch (error) {
        console.error('Error creating map:', error)
        return NextResponse.json({ error: 'Failed to create map' }, { status: 500 })
    }
}

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
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

        const maps = await getProjectMaps(user.uid, resolvedParams.id)
        return NextResponse.json({ maps })
    } catch (error) {
        console.error('Error fetching maps:', error)
        return NextResponse.json({ error: 'Failed to fetch maps' }, { status: 500 })
    }
}
