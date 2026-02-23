'use client'

import { useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'

interface PreviewData {
    sheets?: string[]
    sheetNames?: string[]
    sheet_names?: string[]
    SheetNames?: string[]
    columns: string[]
    availableParameters: string[]
    rowCount: number
    sampleData: any[]
}

const VERCEL_SAFE_LIMIT = 4 * 1024 * 1024

const uploadWithProgress = (
    url: string,
    body: FormData,
    onProgress: (progress: number) => void
): Promise<{ data: any; status: number }> => {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()

        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
                const progress = Math.round((event.loaded / event.total) * 100)
                onProgress(progress)
            }
        })

        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const data = JSON.parse(xhr.responseText)
                    resolve({ data, status: xhr.status })
                } catch {
                    resolve({ data: xhr.responseText, status: xhr.status })
                }
            } else {
                reject(new Error(`Upload failed with status ${xhr.status}: ${xhr.statusText}`))
            }
        })

        xhr.addEventListener('error', () => {
            reject(new Error('Upload failed - network error'))
        })

        xhr.addEventListener('abort', () => {
            reject(new Error('Upload aborted'))
        })

        xhr.open('POST', url)
        xhr.send(body)
    })
}

const getPythonServiceUrl = async (): Promise<string | null> => {
    try {
        const response = await fetch('/api/preview')
        if (response.ok) {
            const data = await response.json()
            return data.pythonServiceUrl
        }
    } catch (err) {
        console.error('Error fetching Python service URL:', err)
    }
    return null
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
    const [uploadProgressMsg, setUploadProgressMsg] = useState('')
    const [uploadProgress, setUploadProgress] = useState(0)

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const selectedFile = e.target.files[0]
            setFile(selectedFile)
            setError('')
            if (!name) {
                const fileName = selectedFile.name.replace(/\.[^/.]+$/, '')
                setName(fileName)
            }
            await fetchPreviewData(selectedFile)
        }
    }

    const fetchPreviewData = async (fileToUpload: File, sheetName?: string) => {
        setLoadingPreview(true)
        setUploadProgressMsg('Reading file locally...')
        setUploadProgress(0)
        setPreviewData(null)

        try {
            if (!user) {
                throw new Error('You must be signed in to upload files')
            }

            const token = await user.getIdToken()

            if (fileToUpload.size > VERCEL_SAFE_LIMIT) {
                setUploadProgressMsg(`Uploading ${(fileToUpload.size / (1024 * 1024)).toFixed(1)}MB file to Python Service...`)
                console.log('[Frontend] File is large (', fileToUpload.size, 'bytes), using direct Python service upload')
                const pythonUrl = await getPythonServiceUrl()

                if (!pythonUrl) {
                    throw new Error('File is too large for Vercel (limit 4.5MB) and Python service is not configured. Please use a smaller file or contact support.')
                }

                console.log('[Frontend] Uploading directly to Python service:', pythonUrl)

                const baseUrl = pythonUrl.replace(/\/$/, '')
                const formData = new FormData()
                formData.append('file', fileToUpload)
                formData.append('use_llamaparse', 'true')
                if (sheetName) {
                    formData.append('sheet_name', sheetName)
                }

                const result = await uploadWithProgress(
                    `${baseUrl}/preview`,
                    formData,
                    (progress) => {
                        setUploadProgress(progress)
                        setUploadProgressMsg(`Uploading: ${progress}%`)
                    }
                )

                if (result.status >= 400) {
                    throw new Error(`Python service error: ${String(result.data).substring(0, 100)}`)
                }

                const data = result.data
                console.log('[Frontend] Python service response:', data)

                setPreviewData({
                    sheets: data.sheets || data.sheet_names || [],
                    columns: data.columns || [],
                    availableParameters: data.numeric_columns || [],
                    rowCount: data.row_count || 0,
                    sampleData: data.preview_data || []
                })

                const sheets = data.sheets || data.sheet_names || []
                if (sheets.length > 0) {
                    setSelectedSheet(sheets[0])
                }

                if (data.numeric_columns && data.numeric_columns.length > 0) {
                    setParameter(data.numeric_columns[0])
                } else if (data.columns && data.columns.length > 0) {
                    setParameter(data.columns[0])
                }

                return
            }

            setUploadProgressMsg('Sending file to API for preview...')
            const formData = new FormData()
            formData.append('file', fileToUpload)
            if (sheetName) {
                formData.append('sheet_name', sheetName)
            }

            const response = await fetch('/api/preview', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            })

            if (response.status === 413) {
                const data = await response.json()
                if (data.requiresDirectUpload && data.pythonServiceUrl) {
                    setUploadProgressMsg('Vercel limit reached. Retrying upload directly to Python service...')
                    console.log('[Frontend] Got 413, retrying with direct Python service upload')

                    const pythonFormData = new FormData()
                    pythonFormData.append('file', fileToUpload)
                    pythonFormData.append('use_llamaparse', 'true')
                    if (sheetName) {
                        pythonFormData.append('sheet_name', sheetName)
                    }
                    const baseUrl = data.pythonServiceUrl.replace(/\/$/, '')

                    const result = await uploadWithProgress(
                        `${baseUrl}/preview`,
                        pythonFormData,
                        (progress) => {
                            setUploadProgress(progress)
                            setUploadProgressMsg(`Uploading: ${progress}%`)
                        }
                    )

                    if (result.status >= 400) {
                        const errorText = String(result.data)
                        throw new Error(`Python service error: ${errorText.substring(0, 100)}`)
                    }

                    const pythonData = result.data
                    setPreviewData({
                        sheets: pythonData.sheets || pythonData.sheet_names || [],
                        columns: pythonData.columns || [],
                        availableParameters: pythonData.numeric_columns || [],
                        rowCount: pythonData.row_count || 0,
                        sampleData: pythonData.preview_data || []
                    })

                    const sheets = pythonData.sheets || pythonData.sheet_names || []
                    if (sheets.length > 0) {
                        setSelectedSheet(sheets[0])
                    }

                    if (pythonData.numeric_columns && pythonData.numeric_columns.length > 0) {
                        setParameter(pythonData.numeric_columns[0])
                    }
                    return
                }
                throw new Error(data.error || 'File too large')
            }

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.error || 'Failed to preview file')
            }

            const data = await response.json()
            setPreviewData(data)

            const sheets = data.sheets || data.sheetNames || []
            if (sheets.length > 0) {
                setSelectedSheet(sheets[0])
            }

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
            setUploadProgressMsg('')
            setUploadProgress(0)
        }
    }

    const handleSheetChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
        const newSheet = e.target.value
        setSelectedSheet(newSheet)
        setParameter('')
        if (file) {
            await fetchPreviewData(file, newSheet)
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

        if (!parameter) {
            setError('Please select a parameter column to map')
            return
        }

        setLoading(true)
        setError('')

        try {
            if (!user) {
                throw new Error('You must be signed in to create maps')
            }

            const token = await user.getIdToken()

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

            setUploading(true)

            if (file.size > VERCEL_SAFE_LIMIT) {
                console.log('[Frontend] File is large for processing, using direct Python service upload')
                const pythonUrl = await getPythonServiceUrl()

                if (!pythonUrl) {
                    throw new Error('File is too large for Vercel (limit 4.5MB) and Python service is not configured.')
                }

                console.log('[Frontend] Processing directly via Python service:', pythonUrl)

                const formData = new FormData()
                formData.append('file', file)
                formData.append('parameter', parameter)
                formData.append('colormap', colormap)

                const baseUrl = pythonUrl.replace(/\/$/, '')
                const processResponse = await fetch(`${baseUrl}/process`, {
                    method: 'POST',
                    body: formData
                })

                if (!processResponse.ok) {
                    const errorText = await processResponse.text()
                    throw new Error(`Python service error: ${errorText.substring(0, 100)}`)
                }

                const result = await processResponse.json()
                console.log('[Frontend] Python process result:', result)

                router.push(`/dashboard/projects/${projectId}/maps/${mapId}`)
                return
            }

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

            if (uploadResponse.status === 413) {
                const data = await uploadResponse.json()
                if (data.requiresDirectUpload && data.pythonServiceUrl) {
                    console.log('[Frontend] Got 413 on process, retrying with direct Python service upload')

                    const pythonFormData = new FormData()
                    pythonFormData.append('file', file)
                    pythonFormData.append('parameter', parameter)
                    pythonFormData.append('colormap', colormap)

                    const baseUrl = data.pythonServiceUrl.replace(/\/$/, '')
                    const pythonResponse = await fetch(`${baseUrl}/process`, {
                        method: 'POST',
                        body: pythonFormData
                    })

                    if (!pythonResponse.ok) {
                        const errorText = await pythonResponse.text()
                        throw new Error(`Python service error: ${errorText.substring(0, 100)}`)
                    }

                    router.push(`/dashboard/projects/${projectId}/maps/${mapId}`)
                    return
                }
                throw new Error(data.error || 'File too large')
            }

            if (!uploadResponse.ok) {
                const data = await uploadResponse.json()
                throw new Error(data.error || 'Failed to process file')
            }

            router.push(`/dashboard/projects/${projectId}/maps/${mapId}`)
        } catch (err) {
            console.error('Error creating map:', err)
            setError(err instanceof Error ? err.message : 'Failed to create map')
        } finally {
            setLoading(false)
            setUploading(false)
        }
    }

    const sheets = previewData?.sheets || previewData?.sheetNames || previewData?.sheet_names || previewData?.SheetNames || []
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
                    <div className="mb-6 py-4 bg-gray-50 rounded-lg">
                        <div className="text-center mb-3">
                            <svg className="animate-spin w-6 h-6 text-primary mx-auto mb-2" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <p className="text-gray-600">{uploadProgressMsg || 'Reading file...'}</p>
                        </div>
                        {uploadProgress > 0 && (
                            <div className="mx-auto max-w-xs">
                                <div className="flex justify-between text-xs text-gray-500 mb-1">
                                    <span>Upload Progress</span>
                                    <span>{uploadProgress}%</span>
                                </div>
                                <div className="w-full bg-gray-200 rounded-full h-2.5">
                                    <div
                                        className="bg-primary h-2.5 rounded-full transition-all duration-300 ease-out"
                                        style={{ width: `${uploadProgress}%` }}
                                    ></div>
                                </div>
                            </div>
                        )}
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
                            {sheets.map((sheet: string) => (
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
