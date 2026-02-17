'use client'

import { useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'

interface PreviewData {
    sheets?: string[]
    sheetNames?: string[]
    columns: string[]
    availableParameters: string[]
    rowCount: number
    sampleData: any[]
}

export default function NewMapPage() {
    const { id: projectId } = useParams()
    const router = useRouter()
    const { user } = useAuth()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const [name, setName] = useState('')
    const [file, setFile] = useState<File | null>(null)
    const [selectedSheet, setSelectedSheet] = useState('')
    const [parameter, setParameter] = useState('')
    const [colormap, setColormap] = useState('viridis')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [uploading, setUploading] = useState(false)
    const [previewData, setPreviewData] = useState<PreviewData | null>(null)
    const [loadingPreview, setLoadingPreview] = useState(false)

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const selectedFile = e.target.files[0]
            setFile(selectedFile)
            setError('')

            if (!name) {
                // Auto-fill name from filename
                const fileName = selectedFile.name.replace(/\.[^/.]+$/, '')
                setName(fileName)
            }

            // Fetch preview data (columns, sheets) from the file
            await fetchPreviewData(selectedFile)
        }
    }

    const fetchPreviewData = async (fileToUpload: File) => {
        setLoadingPreview(true)
        setPreviewData(null)

        try {
            const token = await user!.getIdToken()

            const formData = new FormData()
            formData.append('file', fileToUpload)

            const response = await fetch('/api/preview', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.error || 'Failed to preview file')
            }

            const data = await response.json()
            setPreviewData(data)

            // Auto-select first sheet if available
            const sheets = data.sheets || data.sheetNames || []
            if (sheets.length > 0) {
                setSelectedSheet(sheets[0])
            }

            // Auto-select first available parameter if any
            if (data.availableParameters && data.availableParameters.length > 0) {
                setParameter(data.availableParameters[0])
            } else if (data.columns && data.columns.length > 0) {
                setParameter(data.columns[0])
            }

        } catch (err) {
            console.error('Error fetching preview:', err)
            setError(err instanceof Error ? err.message : 'Failed to read file')
        } finally {
            setLoadingPreview(false)
        }
    }

    const handleSheetChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setSelectedSheet(e.target.value)
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

        if (!parameter) {
            setError('Please select a parameter column to map')
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
            formData.append('projectId', projectId as string)
            formData.append('parameter', parameter)
            formData.append('colormap', colormap)
            if (selectedSheet) {
                formData.append('sheet', selectedSheet)
            }

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

    // Get sheets from preview data
    const sheets = previewData?.sheets || previewData?.sheetNames || []
    const isExcelFile = file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))
    const showSheetDropdown = isExcelFile && sheets.length > 1

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

                {loadingPreview && (
                    <div className="mb-6 text-center py-4 bg-gray-50 rounded-lg">
                        <svg className="animate-spin w-6 h-6 text-primary mx-auto mb-2" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <p className="text-gray-600">Reading file...</p>
                    </div>
                )}

                {showSheetDropdown && (
                    <div className="mb-6">
                        <label htmlFor="sheet" className="block font-medium text-gray-700 mb-2">Select Sheet *</label>
                        <select
                            id="sheet"
                            value={selectedSheet}
                            onChange={handleSheetChange}
                            required
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-primary transition-colors"
                        >
                            {sheets.map((sheet) => (
                                <option key={sheet} value={sheet}>
                                    {sheet}
                                </option>
                            ))}
                        </select>
                        <p className="text-sm text-gray-500 mt-1">Select the sheet containing your data</p>
                    </div>
                )}

                {previewData && (previewData.availableParameters?.length > 0 || previewData.columns?.length > 0) && (
                    <div className="mb-6">
                        <label htmlFor="parameter" className="block font-medium text-gray-700 mb-2">
                            Parameter to Map *
                            {previewData.availableParameters && previewData.availableParameters.length > 0 && (
                                <span className="text-sm text-gray-500 font-normal ml-2">(Numeric columns suggested)</span>
                            )}
                        </label>
                        <select
                            id="parameter"
                            value={parameter}
                            onChange={(e) => setParameter(e.target.value)}
                            required
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-primary transition-colors"
                        >
                            <option value="">-- Select Parameter --</option>
                            {(previewData.availableParameters?.length > 0 ? previewData.availableParameters : previewData.columns || []).map((col) => (
                                <option key={col} value={col}>
                                    {col}
                                </option>
                            ))}
                        </select>
                        <p className="text-sm text-gray-500 mt-1">Column containing the values to visualize on the map</p>
                    </div>
                )}

                {!previewData && file && !loadingPreview && (
                    <div className="mb-6">
                        <label htmlFor="parameter" className="block font-medium text-gray-700 mb-2">Parameter *</label>
                        <input
                            type="text"
                            id="parameter"
                            value={parameter}
                            onChange={(e) => setParameter(e.target.value)}
                            placeholder="e.g., GWL, Depth, Level"
                            required
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-primary transition-colors"
                        />
                        <p className="text-sm text-gray-500 mt-1">Column name in your Excel file for the values to map</p>
                    </div>
                )}

                <div className="mb-6">
                    <label htmlFor="colormap" className="block font-medium text-gray-700 mb-2">Color Scheme</label>
                    <select
                        id="colormap"
                        value={colormap}
                        onChange={(e) => setColormap(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-primary transition-colors"
                    >
                        <option value="viridis">Viridis (Purple → Yellow)</option>
                        <option value="plasma">Plasma (Purple → Orange → Yellow)</option>
                        <option value="RdYlBu_r">Red-Yellow-Blue (Reversed)</option>
                        <option value="RdYlBu">Red-Yellow-Blue</option>
                        <option value="blues">Blues</option>
                        <option value="greens">Greens</option>
                        <option value="reds">Reds</option>
                        <option value="YlOrRd">Yellow-Orange-Red</option>
                        <option value="YlGn">Yellow-Green</option>
                        <option value="YlGnBu">Yellow-Green-Blue</option>
                        <option value="BuPu">Blue-Purple</option>
                        <option value="GnBu">Green-Blue</option>
                        <option value="OrRd">Orange-Red</option>
                        <option value="PuBu">Purple-Blue</option>
                        <option value="PuRd">Purple-Red</option>
                        <option value="BrBG">Brown-Blue-Green</option>
                        <option value="PRGn">Purple-Green</option>
                        <option value="PiYG">Pink-Yellow-Green</option>
                        <option value="inferno">Inferno</option>
                        <option value="magma">Magma</option>
                        <option value="cividis">Cividis</option>
                        <option value="Spectral_r">Spectral (Reversed)</option>
                        <option value="coolwarm">Coolwarm</option>
                    </select>
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
                    disabled={loading || uploading || loadingPreview}
                    className="w-full px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                    {loading || uploading || loadingPreview ? (
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
