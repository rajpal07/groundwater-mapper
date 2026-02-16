'use client'

import { useEffect, useState, use } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'

interface Map {
  id: string
  name: string
  type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  createdAt: string
  outputUrl?: string
}

interface Project {
  id: string
  name: string
  description: string
  createdAt: string
  maps: Map[]
}

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { user } = useAuth()
  const router = useRouter()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const resolvedParams = use(params)

  useEffect(() => {
    const fetchProject = async () => {
      if (!user) return

      try {
        const token = await user.getIdToken()
        const response = await fetch(`/api/projects/${resolvedParams.id}`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (!response.ok) {
          throw new Error('Failed to fetch project')
        }

        const data = await response.json()
        setProject(data.project)
      } catch (err) {
        console.error('Error fetching project:', err)
        setError('Failed to load project')
      } finally {
        setLoading(false)
      }
    }

    if (user) {
      fetchProject()
    }
  }, [user, resolvedParams.id])

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
      return
    }

    try {
      const token = await user!.getIdToken()
      const response = await fetch(`/api/projects/${resolvedParams.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        throw new Error('Failed to delete project')
      }

      router.push('/dashboard')
    } catch (err) {
      console.error('Error deleting project:', err)
      setError('Failed to delete project')
    }
  }

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading project...</p>
      </div>
    )
  }

  if (error && !project) {
    return (
      <div className="error-container">
        <p>{error}</p>
        <button onClick={() => router.push('/dashboard')}>Go Back</button>
      </div>
    )
  }

  return (
    <div className="project-detail-page">
      <div className="page-header">
        <div className="header-info">
          <h1>{project?.name}</h1>
          <p>{project?.description || 'No description'}</p>
        </div>
        <div className="header-actions">
          <button onClick={handleDelete} className="btn-danger">
            Delete Project
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="maps-section">
        <h2>Maps</h2>

        {(project?.maps?.length ?? 0) === 0 ? (
          <div className="empty-state">
            <p>No maps yet. Upload data to create your first map.</p>
          </div>
        ) : (
          <div className="maps-grid">
            {project?.maps.map((map) => (
              <div key={map.id} className={`map-card status-${map.status}`}>
                <div className="map-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                    <circle cx="12" cy="10" r="3"></circle>
                  </svg>
                </div>
                <div className="map-info">
                  <h3>{map.name}</h3>
                  <p>Type: {map.type}</p>
                  <span className={`status-badge ${map.status}`}>{map.status}</span>
                </div>
                {map.outputUrl && (
                  <a href={map.outputUrl} target="_blank" rel="noopener noreferrer" className="view-btn">
                    View Map
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <style jsx>{`
        .project-detail-page {
          padding: 2rem;
          max-width: 1200px;
          margin: 0 auto;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 2rem;
          padding-bottom: 2rem;
          border-bottom: 1px solid #e5e7eb;
        }

        .header-info h1 {
          font-size: 1.75rem;
          color: #1f2937;
          margin: 0 0 0.5rem;
        }

        .header-info p {
          color: #6b7280;
          margin: 0;
        }

        .btn-danger {
          padding: 0.5rem 1rem;
          background: #fee2e2;
          border: none;
          border-radius: 6px;
          color: #dc2626;
          cursor: pointer;
          transition: background 0.2s;
        }

        .btn-danger:hover {
          background: #fecaca;
        }

        .error-message {
          background: #fee2e2;
          color: #dc2626;
          padding: 1rem;
          border-radius: 8px;
          margin-bottom: 2rem;
        }

        .maps-section h2 {
          font-size: 1.25rem;
          color: #1f2937;
          margin-bottom: 1rem;
        }

        .empty-state {
          padding: 2rem;
          background: #f9fafb;
          border-radius: 8px;
          text-align: center;
        }

        .empty-state p {
          color: #6b7280;
          margin: 0;
        }

        .maps-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 1rem;
        }

        .map-card {
          display: flex;
          gap: 1rem;
          padding: 1.25rem;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 10px;
        }

        .map-icon {
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #E3F3F1;
          border-radius: 8px;
          color: #006645;
        }

        .map-info h3 {
          margin: 0 0 0.25rem;
          font-size: 1rem;
          color: #1f2937;
        }

        .map-info p {
          margin: 0 0 0.5rem;
          font-size: 0.875rem;
          color: #6b7280;
        }

        .status-badge {
          display: inline-block;
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          font-size: 0.75rem;
          font-weight: 500;
        }

        .status-badge.pending { background: #fef3c7; color: #d97706; }
        .status-badge.processing { background: #dbeafe; color: #2563eb; }
        .status-badge.completed { background: #d1fae5; color: #059669; }
        .status-badge.failed { background: #fee2e2; color: #dc2626; }

        .view-btn {
          display: block;
          margin-top: 0.75rem;
          padding: 0.5rem 1rem;
          background: #006645;
          color: white;
          text-align: center;
          border-radius: 6px;
          text-decoration: none;
          font-size: 0.875rem;
        }

        .view-btn:hover {
          background: #00493D;
        }

        .loading-container,
        .error-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 60vh;
          gap: 1rem;
        }

        .spinner {
          width: 40px;
          height: 40px;
          border: 3px solid #e5e7eb;
          border-top-color: #006645;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
