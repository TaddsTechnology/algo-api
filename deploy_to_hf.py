#!/usr/bin/env python3
"""
Deploy to Hugging Face Space
Auto-commit and push changes to trigger rebuild
"""

import subprocess
import sys
from datetime import datetime
import os

# Configuration
HF_TOKEN = os.getenv("HF_TOKEN")
HF_USERNAME = "TaddsTeam"
HF_SPACE = "algo"

if not HF_TOKEN:
    print("❌ HF_TOKEN environment variable is required!")
    print("Set it with: $env:HF_TOKEN='your_token_here'")
    sys.exit(1)

def run_command(cmd, check=True):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=True,
            text=True
        )
        return result.stdout.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        return e.stderr.strip(), e.returncode

def main():
    print("🚀 Deploying to Hugging Face Space...")
    print("=" * 50)
    
    # Check if we're in a git repo
    if not os.path.exists('.git'):
        print("❌ Not a git repository!")
        sys.exit(1)
    
    # Set git remote with token
    print("🔧 Configuring git remote...")
    remote_url = f"https://{HF_USERNAME}:{HF_TOKEN}@huggingface.co/spaces/{HF_USERNAME}/{HF_SPACE}"
    run_command(f'git remote set-url origin {remote_url}')
    
    # Check for changes
    print("📋 Checking for changes...")
    status, _ = run_command('git status --porcelain')
    
    if status:
        print("📝 Changes detected, adding files...")
        run_command('git add .')
        
        commit_message = f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"💾 Committing changes: {commit_message}")
        run_command(f'git commit -m "{commit_message}"')
    else:
        print("✅ No changes to commit")
    
    # Push to Hugging Face
    print("⬆️  Pushing to Hugging Face Space...")
    output, returncode = run_command('git push origin main', check=False)
    
    if returncode == 0:
        print()
        print("✅ Successfully deployed to Hugging Face!")
        print(f"🌐 Your Space: https://huggingface.co/spaces/{HF_USERNAME}/{HF_SPACE}")
        print("🔄 Build will start automatically...")
        print()
    else:
        print()
        print("❌ Push failed!")
        print(output)
        sys.exit(1)
    
    print("✨ Deployment complete!")

if __name__ == "__main__":
    main()