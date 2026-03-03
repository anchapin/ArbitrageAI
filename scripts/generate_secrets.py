#!/usr/bin/env python3
"""
Generate Secure Random Secrets for ArbitrageAI

This script generates cryptographically secure random secrets for:
- JWT_SECRET_KEY
- CLIENT_AUTH_SECRET
- DATABASE_ENCRYPTION_KEY
- Other sensitive configuration values

Usage:
    python scripts/generate_secrets.py

The generated secrets are stored in data/.secrets with secure permissions (0o600).
"""

import json
import secrets
import sys
from pathlib import Path


# Secure secrets file location
SECRETS_FILE = Path("data/.secrets")


def generate_secure_secret() -> str:
    """Generate a cryptographically secure random secret."""
    return secrets.token_hex(32)  # 256-bit secret (64 hex characters)


def main():
    """Generate new secure secrets."""
    # Check if secrets file already exists
    if SECRETS_FILE.exists():
        print(f"⚠️  Secrets file already exists at: {SECRETS_FILE}")
        response = input("Do you want to overwrite existing secrets? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Aborted. Existing secrets preserved.")
            sys.exit(0)
    
    # Generate new secrets
    print("🔐 Generating cryptographically secure secrets...")
    
    new_secrets = {
        "JWT_SECRET_KEY": generate_secure_secret(),
        "CLIENT_AUTH_SECRET": generate_secure_secret(),
        "DATABASE_ENCRYPTION_KEY": generate_secure_secret(),
    }
    
    # Create directory if it doesn't exist
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Write secrets to file
    with open(SECRETS_FILE, 'w') as f:
        json.dump(new_secrets, f, indent=2)
    
    # Set secure permissions (owner read/write only)
    SECRETS_FILE.chmod(0o600)
    
    # Display success message
    print("\n" + "="*70)
    print("✅ SECRETS GENERATED SUCCESSFULLY")
    print("="*70)
    print(f"\n📁 Secrets saved to: {SECRETS_FILE.absolute()}")
    print(f"🔒 File permissions: 0o600 (owner read/write only)")
    print(f"📊 Secrets generated: {len(new_secrets)}")
    
    print("\n" + "="*70)
    print("⚠️  IMPORTANT SECURITY REMINDERS")
    print("="*70)
    print("1. 📦 Back up this file securely (e.g., password manager, secure vault)")
    print("2. 🔐 Never commit secrets to version control (already in .gitignore)")
    print("3. 🚀 Set environment variables in production from these secrets")
    print("4. 🔄 Rotate secrets periodically (run this script again)")
    print("5. 👥 Restrict access to data/.secrets file (chmod 600)")
    
    print("\n" + "="*70)
    print("📋 NEXT STEPS")
    print("="*70)
    print("1. Back up the secrets file")
    print("2. In production, set environment variables:")
    print("   export JWT_SECRET_KEY=<value>")
    print("   export CLIENT_AUTH_SECRET=<value>")
    print("   export DATABASE_ENCRYPTION_KEY=<value>")
    print("3. Restart the application")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
