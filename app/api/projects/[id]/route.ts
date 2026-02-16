import { NextRequest, NextResponse } from 'next/server'
import { verifyFirebaseToken, getProjectWithMaps, deleteProject } from '@/lib/firebase-admin'

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

        const project = await getProjectWithMaps(user.uid, resolvedParams.id)

        if (!project) {
            return NextResponse.json({ error: 'Project not found' }, { status: 404 })
        }

        return NextResponse.json({ project })
    } catch (error) {
        console.error('Error fetching project:', error)
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
    }
}

export async function DELETE(
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

        const project = await getProjectWithMaps(user.uid, resolvedParams.id)

        if (!project) {
            return NextResponse.json({ error: 'Project not found' }, { status: 404 })
        }

        await deleteProject(user.uid, resolvedParams.id)

        return NextResponse.json({ success: true })
    } catch (error) {
        console.error('Error deleting project:', error)
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
    }
}
