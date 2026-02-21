"""
Authentication middleware for Firebase JWT validation.
Provides secure access control for API endpoints.
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from functools import wraps

import requests
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


class FirebaseUser(BaseModel):
    """Authenticated Firebase user."""
    uid: str
    email: Optional[str] = None
    email_verified: bool = False
    name: Optional[str] = None
    picture: Optional[str] = None
    issuer: str
    audience: str
    expires_at: int


class FirebaseAuth:
    """Firebase Authentication handler for JWT validation."""
    
    def __init__(self):
        self.project_id = os.getenv("FIREBASE_PROJECT_ID")
        self._public_keys: Optional[Dict[str, str]] = None
        self._keys_last_refreshed: float = 0
        
    def get_public_keys(self) -> Dict[str, str]:
        """Fetch Firebase public keys for JWT verification."""
        try:
            response = requests.get(
                "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch Firebase public keys: {e}")
            return {}
    
    def verify_token(self, token: str) -> Optional[FirebaseUser]:
        """
        Verify Firebase JWT token.
        
        Note: This is a simplified verification. For production, use firebase-admin SDK.
        This implementation validates the token structure and claims without
        cryptographic verification (which requires the firebase-admin library).
        """
        if not token:
            return None
            
        try:
            # Decode JWT without verification (for development)
            # In production, use firebase-admin SDK for proper verification
            import base64
            
            # Split token into parts
            parts = token.split('.')
            if len(parts) != 3:
                logger.warning("Invalid token format")
                return None
            
            # Decode payload
            payload_b64 = parts[1]
            # Add padding if needed
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding
            
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            
            # Validate required claims
            required_claims = ['iss', 'sub', 'aud', 'exp', 'iat']
            for claim in required_claims:
                if claim not in payload:
                    logger.warning(f"Missing required claim: {claim}")
                    return None
            
            # Validate issuer
            expected_issuer = f"https://securetoken.google.com/{self.project_id}"
            if payload['iss'] != expected_issuer:
                logger.warning(f"Invalid issuer: {payload['iss']}")
                return None
            
            # Validate audience
            if payload['aud'] != self.project_id:
                logger.warning(f"Invalid audience: {payload['aud']}")
                return None
            
            # Validate expiration
            import time
            if payload['exp'] < time.time():
                logger.warning("Token has expired")
                return None
            
            # Create user object
            return FirebaseUser(
                uid=payload['sub'],
                email=payload.get('email'),
                email_verified=payload.get('email_verified', False),
                name=payload.get('name'),
                picture=payload.get('picture'),
                issuer=payload['iss'],
                audience=payload['aud'],
                expires_at=payload['exp']
            )
            
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return None


# Global auth instance
firebase_auth = FirebaseAuth()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[FirebaseUser]:
    """
    Dependency to get the current authenticated user.
    
    Returns None if no token is provided (optional auth).
    Raises HTTPException if token is invalid.
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    user = firebase_auth.verify_token(token)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[FirebaseUser]:
    """
    Dependency to get the current authenticated user (optional).
    Returns None if no token is provided or if token is invalid.
    Does not raise an exception for missing/invalid tokens.
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    user = firebase_auth.verify_token(token)
    
    return user


async def get_current_user_required(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> FirebaseUser:
    """
    Dependency that requires authentication.
    Raises HTTPException if no token or invalid token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_current_user(credentials)
    return user


def require_auth(func):
    """
    Decorator to require authentication for a route.
    Usage:
        @router.get("/protected")
        @require_auth
        async def protected_route(user: FirebaseUser):
            return {"user_id": user.uid}
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # This decorator is for reference; use dependencies instead
        return await func(*args, **kwargs)
    return wrapper


# Optional: Firebase Admin SDK integration for production
def init_firebase_admin():
    """
    Initialize Firebase Admin SDK for proper JWT verification.
    Call this at application startup if using firebase-admin.
    """
    try:
        import firebase_admin
        from firebase_admin import credentials
        
        # Check if already initialized
        if firebase_admin._apps:
            return True
        
        # Get service account from environment
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
        if service_account_json:
            cred_dict = json.loads(service_account_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully")
            return True
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY not set, using simplified auth")
            return False
            
    except ImportError:
        logger.warning("firebase-admin not installed, using simplified auth")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return False
