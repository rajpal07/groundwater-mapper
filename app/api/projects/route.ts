import { NextResponse } from 'next/server'
import { verifyIdToken, getUserProjects, createProject, deleteProject } from '@/lib/firebase-admin'

export const dynamic = 'force-dynamic'

// Get all projects for the authenticated user
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
        const projects = await getUserProjects(userId)

        return NextResponse.json({ projects })
    } catch (error) {
        console.error('Error fetching projects:', error)
        return NextResponse.json({ error: 'Failed to fetch projects' }, { status: 500 })
    }
}

// Create a new project
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
        const { name, description } = body

        if (!name) {
            return NextResponse.json({ error: 'Project name is required' }, { status: 400 })
        }

        const project = await createProject(userId, { name, description })
        return NextResponse.json(project)
    } catch (error) {
        console.error('Error creating project:', error)
        return NextResponse.json({ error: 'Failed to create project' }, { status: 500 })
    }
}

// Delete a project
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
        const projectId = searchParams.get('id')

        if (!projectId) {
            return NextResponse.json({ error: 'Project ID required' }, { status: 400 })
        }

        await deleteProject(userId, projectId)
        return NextResponse.json({ success: true })
    } catch (error) {
        console.error('Error deleting project:', error)
        return NextResponse.json({ error: 'Failed to delete project' }, { status: 500 })
    }
}
