import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import * as fs from 'fs'
import * as path from 'path'
import os from 'os'

export async function POST(request: Request) {
    try {
        const session = await getServerSession(authOptions)

        if (!session?.user?.email) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const formData = await request.formData()
        const file = formData.get('file') as File

        if (!file) {
            return NextResponse.json({ error: 'No file provided' }, { status: 400 })
        }

        // Save uploaded file temporarily
        const tempDir = os.tmpdir()
        const tempFilePath = path.join(tempDir, `preview_${Date.now()}.xlsx`)
        const buffer = Buffer.from(await file.arrayBuffer())
        fs.writeFileSync(tempFilePath, buffer)

        // Read Excel file with pandas-like approach using xlsx library
        // Since we can't use Python here, we'll use a JavaScript approach
        const XLSX = require('xlsx')
        const workbook = XLSX.readFile(tempFilePath)
        const sheetName = workbook.SheetNames[0]
        const worksheet = workbook.Sheets[sheetName]
        const data = XLSX.utils.sheet_to_json(worksheet, { header: 1 })

        // Clean up temp file
        try {
            fs.unlinkSync(tempFilePath)
        } catch (e) {
            console.error('Failed to delete temp file:', e)
        }

        if (!data || data.length === 0) {
            return NextResponse.json({ error: 'Empty file' }, { status: 400 })
        }

        // Get headers (first row)
        const headers = data[0] as string[]
        const columns = headers.map(h => String(h).trim()).filter(h => h)

        // Get preview data (first 10 rows)
        const preview = data.slice(1, 11).map((row: any[]) => {
            const obj: Record<string, any> = {}
            headers.forEach((header, i) => {
                obj[String(header).trim()] = row[i]
            })
            return obj
        })

        return NextResponse.json({
            columns,
            preview,
            rows: data.length - 1
        })
    } catch (error) {
        console.error('Error previewing file:', error)
        return NextResponse.json({ error: 'Failed to read file' }, { status: 500 })
    }
}
