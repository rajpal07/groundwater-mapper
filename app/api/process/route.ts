import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/db'
import { spawn } from 'child_process'
import * as fs from 'fs'
import * as path from 'path'
import os from 'os'

export const dynamic = 'force-dynamic'

export async function POST(request: Request): Promise<NextResponse> {
    try {
        const session = await getServerSession(authOptions)

        if (!session?.user?.email) {
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
        const user = await prisma.user.findUnique({
            where: { email: session.user.email }
        })

        if (!user) {
            return NextResponse.json({ error: 'User not found' }, { status: 404 })
        }

        const project = await prisma.project.findFirst({
            where: {
                id: projectId,
                userId: user.id
            }
        })

        if (!project) {
            return NextResponse.json({ error: 'Project not found' }, { status: 404 })
        }

        // Save uploaded file temporarily
        const tempDir = os.tmpdir()
        const tempFilePath = path.join(tempDir, `upload_${Date.now()}.xlsx`)
        const buffer = Buffer.from(await file.arrayBuffer())
        fs.writeFileSync(tempFilePath, buffer)

        // Call Python script for processing
        const pythonScript = path.join(process.cwd(), 'scripts', 'process_map.py')

        // Create Python virtual environment path
        const venvPython = process.platform === 'win32'
            ? path.join(process.cwd(), 'venv', 'Scripts', 'python.exe')
            : path.join(process.cwd(), 'venv', 'bin', 'python')

        // Run Python script synchronously
        const { execSync } = require('child_process')

        try {
            const output = execSync(`"${venvPython}" "${pythonScript}" --input "${tempFilePath}" --parameter "${parameter}" --colormap ${colormap}`, {
                cwd: path.join(process.cwd(), 'scripts'),
                encoding: 'utf-8',
                timeout: 120000
            })

            // Clean up temp file
            try {
                fs.unlinkSync(tempFilePath)
            } catch (e) {
                console.error('Failed to delete temp file:', e)
            }

            try {
                const result = JSON.parse(output)
                return NextResponse.json(result)
            } catch (e) {
                console.error('Failed to parse output:', output)
                return NextResponse.json({
                    error: 'Failed to parse results',
                    rawOutput: output
                }, { status: 500 })
            }
        } catch (execError: any) {
            // Clean up temp file
            try {
                fs.unlinkSync(tempFilePath)
            } catch (e) {
                console.error('Failed to delete temp file:', e)
            }

            console.error('Python script error:', execError.message)
            return NextResponse.json({
                error: 'Processing failed',
                details: execError.message
            }, { status: 500 })
        }
    } catch (error: any) {
        console.error('Error processing map:', error)
        return NextResponse.json({ error: error.message || 'Failed to process map' }, { status: 500 })
    }
}
