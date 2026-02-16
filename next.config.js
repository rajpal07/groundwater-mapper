/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    images: {
        domains: ['lh3.googleusercontent.com'],
    },
    experimental: {
        serverActions: {
            bodySizeLimit: '50mb',
        },
    },
}

module.exports = nextConfig
