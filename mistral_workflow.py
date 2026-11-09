#!/usr/bin/env python3
"""
News Digest Workflow for Mistral Cloud Platform
This file is designed to run as a Mistral Cloud workflow.
"""

import os
import sys
import yaml
import json
from news_digest_v2 import NewsDigestWorkflow
from datetime import datetime

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """
    Main entry point for Mistral Cloud workflow.
    """
    print("Starting News Digest Workflow on Mistral Cloud")

    try:
        # Initialize workflow
        workflow = NewsDigestWorkflow()

        # Run the workflow
        result = workflow.run()

        if result.get('status') == 'success':
            print(f"Workflow executed successfully")
            print(f"Generated {len(result.get('digests', []))} digests")
            print(f"Generated {len(result.get('audio_files', []))} audio files")

            # Return data for Mistral Cloud
            return {
                'status': 'success',
                'message': 'News digest generated successfully',
                'digests_count': len(result.get('digests', [])),
                'audio_files_count': len(result.get('audio_files', [])),
                'timestamp': datetime.now().isoformat(),
                'email': result.get('email', {})
            }
        else:
            return {
                'status': 'error',
                'message': result.get('error', 'Unknown error')
            }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

if __name__ == '__main__':
    result = main()
    print("\n" + "="*60)
    print("WORKFLOW RESULT")
    print("="*60)
    for key, value in result.items():
        print(f"{key}: {value}")
    print("="*60)
