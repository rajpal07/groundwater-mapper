'use client'

import { useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'

export default function NewMapPage() {
    const { id: projectId } = useParams()
    const router = useRouter()
    const { user } = useAuth()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const [name, setName] = useState('')
    const [file, setFile] = useState<File | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [uploading, setUploading] = useState(false)

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0])
            if (!name) {
                // Auto-fill name from filename
                const fileName = e.target.files[0].name.replace(/\.[^/.]+$/, '')
                setName(fileName)
            }
        }
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!name.trim()) {
            setError('Map name is required')
            return
        }

        if (!file) {
            setError('Please select a data file (CSV or Excel)')
            return
        }

        setLoading(true)
        setError('')

        try {
            const token = await user!.getIdToken()

            // Step 1: Create the map first
            const createResponse = await fetch(`/api/projects/${projectId}/maps`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ name: name.trim() })
            })

            if (!createResponse.ok) {
                const data = await createResponse.json()
                throw new Error(data.error || 'Failed to create map')
            }

            const mapData = await createResponse.json()
            const mapId = mapData.id

            // Step 2: Upload the file
            setUploading(true)
            const formData = new FormData()
            formData.append('file', file)
            formData.append('mapId', mapId)

            const uploadResponse = await fetch('/api/process', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            })

            if (!uploadResponse.ok) {
                const data = await uploadResponse.json()
                throw new Error(data.error || 'Failed to process file')
            }

            // Redirect to the map detail page
            router.push(`/dashboard/projects/${projectId}/maps/${mapId}`)
        } catch (err) {
            console.error('Error creating map:', err)
            setError(err instanceof Error ? err.message : 'Failed to create map')
        } finally {
            setLoading(false)
            setUploading(false)
        }
    }

    return (
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Link
                href={`/dashboard/projects/${projectId}`}
                className="text-primary hover:text-primary-dark font-medium mb-6 inline-block"
            >
                ← Back to Project
            </Link>

            <div className="mb-8">
                <h1 className="text-2xl font-bold text-gray-800 mb-2">Create New Map</h1>
                <p className="text-gray-600">Upload your groundwater data to generate an interactive map</p>
            </div>

            <form onSubmit={handleSubmit} className="bg-white p-8 rounded-xl border border-gray-200">
                {error && (
                    <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6">
                        {error}
                    </div>
                )}

                <div className="mb-6">
                    <label htmlFor="name" className="block font-medium text-gray-700 mb-2">Map Name *</label>
                    <input
                        type="text"
                        id="name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g., Site A - Q3 2024"
                        required
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-primary transition-colors"
                    />
                </div>

                <div className="mb-6">
                    <label className="block font-medium text-gray-700 mb-2">Data File *</label>
                    <div
                        className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-primary transition-colors"
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".csv,.xlsx,.xls"
                            onChange={handleFileChange}
                            className="hidden"
                        />
                        {file ? (
                            <div>
                                <svg className="w-12 h-12 text-green-500 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <p className="font-medium text-gray-800">{file.name}</p>
                                <p className="text-sm text-gray-500">Click to change file</p>
                            </div>
                        ) : (
                            <div>
                                <svg className="w-12 h-12 text-gray-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                                <p className="font-medium text-gray-600">Click to upload data file</p>
                                <p className="text-sm text-gray-500">Supports CSV, Excel (.xlsx, .xls)</p>
                            </div>
                        )}
                    </div>
                </div>

                <div className="bg-blue-50 rounded-lg p-4 mb-6">
                    <h3 className="font-medium text-blue-800 mb-2">Expected Data Format</h3>
                    <p className="text-sm text-blue-700">
                        Your data file should contain columns for:
                    </p>
                    <ul className="text-sm text-blue-700 list-disc list-inside mt-2">
                        <li>Latitude/Longitude coordinates</li>
                        <li>Well ID or Site Name</li>
                        <li>Groundwater level/depth readings</li>
                    </ul>
                </div>

                <button
                    type="submit"
                    disabled={loading || uploading}
                    className="w-full px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                    {loading || uploading ? (
                        <>
                            <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            {uploading ? 'Processing data...' : 'Creating map...'}
                        </>
                    ) : (
                        'Create Map'
                    )}
                </button>
            </form>
        </div>
    )
}
