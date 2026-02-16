'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'

interface Project {
    id: string
    name: string
    description: string
    createdAt: string
    mapCount: number
}

export default function DashboardPage() {
    const { user, loading: authLoading } = useAuth()
    const [projects, setProjects] = useState<Project[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    useEffect(() => {
        const fetchProjects = async () => {
            if (!user) return

            try {
                const token = await user.getIdToken()
                const response = await fetch('/api/projects', {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                })

                if (!response.ok) {
                    throw new Error('Failed to fetch projects')
                }

                const data = await response.json()
                setProjects(data.projects || [])
            } catch (err) {
                console.error('Error fetching projects:', err)
                setError('Failed to load projects')
            } finally {
                setLoading(false)
            }
        }

        if (user) {
            fetchProjects()
        }
    }, [user])

    if (authLoading || loading) {
        return (
            <div className="loading-container">
                <div className="spinner"></div>
                <p>Loading your dashboard...</p>
            </div>
        )
    }

    return (
        <div className="dashboard-home">
            <div className="dashboard-hero">
                <h1>Welcome to Groundwater Mapper</h1>
                <p>Create and manage your groundwater mapping projects</p>

                <Link href="/dashboard/projects/new" className="create-btn">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="12" y1="5" x2="12" y2="19"></line>
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                    Create New Project
                </Link>
            </div>

            {error && (
                <div className="error-message">{error}</div>
            )}

            <div className="projects-section">
                <h2>Your Projects</h2>

                {projects.length === 0 ? (
                    <div className="empty-state">
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                        </svg>
                        <h3>No projects yet</h3>
                        <p>Create your first project to start mapping groundwater data</p>
                        <Link href="/dashboard/projects/new" className="create-btn-outline">
                            Create Project
                        </Link>
                    </div>
                ) : (
                    <div className="projects-grid">
                        {projects.map((project) => (
                            <Link key={project.id} href={`/dashboard/projects/${project.id}`} className="project-card">
                                <div className="project-icon">
                                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                                        <circle cx="12" cy="10" r="3"></circle>
                                    </svg>
                                </div>
                                <div className="project-info">
                                    <h3>{project.name}</h3>
                                    <p>{project.description || 'No description'}</p>
                                    <span className="project-meta">
                                        {project.mapCount || 0} maps · {new Date(project.createdAt).toLocaleDateString()}
                                    </span>
                                </div>
                            </Link>
                        ))}
                    </div>
                )}
            </div>

            <style jsx>{`
        .dashboard-home {
          padding: 2rem;
          max-width: 1200px;
          margin: 0 auto;
        }

        .dashboard-hero {
          text-align: center;
          padding: 3rem 2rem;
          background: linear-gradient(135deg, #00493D 0%, #006645 100%);
          border-radius: 16px;
          color: white;
          margin-bottom: 2rem;
        }

        .dashboard-hero h1 {
          font-size: 2rem;
          margin: 0 0 0.5rem;
        }

        .dashboard-hero p {
          opacity: 0.9;
          margin: 0 0 1.5rem;
        }

        .create-btn {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.875rem 1.5rem;
          background: white;
          color: #00493D;
          border-radius: 8px;
          font-weight: 600;
          text-decoration: none;
          transition: transform 0.2s;
        }

        .create-btn:hover {
          transform: translateY(-2px);
        }

        .error-message {
          background: #fee2e2;
          color: #dc2626;
          padding: 1rem;
          border-radius: 8px;
          margin-bottom: 2rem;
        }

        .projects-section h2 {
          font-size: 1.5rem;
          color: #1f2937;
          margin-bottom: 1.5rem;
        }

        .empty-state {
          text-align: center;
          padding: 4rem 2rem;
          background: #f9fafb;
          border-radius: 12px;
        }

        .empty-state h3 {
          margin: 1rem 0 0.5rem;
          color: #374151;
        }

        .empty-state p {
          color: #6b7280;
          margin: 0 0 1.5rem;
        }

        .create-btn-outline {
          display: inline-block;
          padding: 0.75rem 1.5rem;
          border: 2px solid #006645;
          color: #006645;
          border-radius: 8px;
          text-decoration: none;
          font-weight: 500;
          transition: all 0.2s;
        }

        .create-btn-outline:hover {
          background: #006645;
          color: white;
        }

        .projects-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 1.5rem;
        }

        .project-card {
          display: flex;
          gap: 1rem;
          padding: 1.5rem;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          text-decoration: none;
          transition: all 0.2s;
        }

        .project-card:hover {
          border-color: #006645;
          box-shadow: 0 4px 12px rgba(0, 102, 69, 0.1);
        }

        .project-icon {
          width: 48px;
          height: 48px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #E3F3F1;
          border-radius: 10px;
          color: #006645;
        }

        .project-info h3 {
          margin: 0 0 0.25rem;
          color: #1f2937;
          font-size: 1.1rem;
        }

        .project-info p {
          margin: 0 0 0.5rem;
          color: #6b7280;
          font-size: 0.875rem;
        }

        .project-meta {
          font-size: 0.75rem;
          color: #9ca3af;
        }

        .loading-container {
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
