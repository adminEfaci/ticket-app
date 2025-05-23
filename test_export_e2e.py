#!/usr/bin/env python3
"""
End-to-End test script for the weekly export system.

This script performs a complete test of the export pipeline:
1. Uploads XLS and PDF files
2. Processes the batch
3. Creates export bundle
4. Validates the export structure and contents
"""

import os
import sys
import json
import zipfile
import csv
from io import StringIO
from pathlib import Path
import requests
from datetime import date
import argparse


class ExportE2ETest:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.token = None
        
    def login(self, username="admin", password="admin"):
        """Login and get auth token"""
        print("🔐 Logging in...")
        response = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code != 200:
            print(f"❌ Login failed: {response.text}")
            return False
            
        self.token = response.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        print("✅ Login successful")
        return True
    
    def upload_files(self, xls_path, pdf_path):
        """Upload XLS and PDF files"""
        print(f"\n📤 Uploading files...")
        print(f"   XLS: {xls_path}")
        print(f"   PDF: {pdf_path}")
        
        with open(xls_path, 'rb') as xls_file, open(pdf_path, 'rb') as pdf_file:
            files = {
                'xls_file': (os.path.basename(xls_path), xls_file, 'application/vnd.ms-excel'),
                'pdf_file': (os.path.basename(pdf_path), pdf_file, 'application/pdf')
            }
            
            response = self.session.post(
                f"{self.base_url}/api/upload/batch",
                files=files
            )
        
        if response.status_code != 200:
            print(f"❌ Upload failed: {response.text}")
            return None
            
        data = response.json()
        print(f"✅ Upload successful - Batch ID: {data['batch_id']}")
        return data['batch_id']
    
    def process_batch(self, batch_id):
        """Process the uploaded batch"""
        print(f"\n⚙️  Processing batch {batch_id}...")
        
        response = self.session.post(
            f"{self.base_url}/api/batch/{batch_id}/process"
        )
        
        if response.status_code != 200:
            print(f"❌ Processing failed: {response.text}")
            return False
            
        data = response.json()
        print(f"✅ Processing complete:")
        print(f"   - Tickets parsed: {data['tickets_parsed']}")
        print(f"   - Valid tickets: {data['tickets_valid']}")
        print(f"   - Invalid tickets: {data['tickets_invalid']}")
        return True
    
    def validate_export(self, start_date):
        """Validate export data before creating bundle"""
        print(f"\n🔍 Validating export data for week of {start_date}...")
        
        response = self.session.post(
            f"{self.base_url}/api/export/validate",
            json={
                "start_date": start_date,
                "export_type": "weekly",
                "include_images": True
            }
        )
        
        if response.status_code != 200:
            print(f"❌ Validation failed: {response.text}")
            return False
            
        data = response.json()
        validation = data["validation"]
        
        print(f"📊 Validation Results:")
        print(f"   - Total tickets: {validation['total_tickets']}")
        print(f"   - Matched images: {validation['matched_images']}")
        print(f"   - Missing images: {validation['missing_images']}")
        print(f"   - Match percentage: {validation['match_percentage']:.1f}%")
        
        if validation['duplicate_tickets']:
            print(f"   ⚠️  Duplicate tickets: {validation['duplicate_tickets']}")
        
        if validation['validation_errors']:
            print(f"   ❌ Validation errors:")
            for error in validation['validation_errors']:
                print(f"      - {error}")
        
        return data["can_export"]
    
    def create_export(self, start_date, force=False):
        """Create export bundle"""
        print(f"\n📦 Creating export bundle for week of {start_date}...")
        
        response = self.session.get(
            f"{self.base_url}/api/export/invoices-bundle/{start_date}",
            params={
                "include_images": True,
                "force": force
            },
            stream=True
        )
        
        if response.status_code != 200:
            print(f"❌ Export creation failed: {response.text}")
            return None
            
        # Save ZIP file
        filename = f"export_{start_date}.zip"
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ Export saved to: {filename}")
        return filename
    
    def validate_zip_structure(self, zip_path):
        """Validate the structure and contents of the export ZIP"""
        print(f"\n🔍 Validating ZIP structure...")
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()
            
            # Check for required files
            required_files = ["merged.csv"]
            for req_file in required_files:
                if req_file not in namelist:
                    print(f"❌ Missing required file: {req_file}")
                    return False
            
            print("✅ Found merged.csv")
            
            # Find week directories
            week_dirs = [name for name in namelist if name.startswith("week_")]
            print(f"✅ Found {len(set(d.split('/')[0] for d in week_dirs))} week directories")
            
            # Validate merged.csv
            with zf.open("merged.csv") as f:
                reader = csv.DictReader(StringIO(f.read().decode('utf-8')))
                rows = list(reader)
                print(f"   - Total rows in merged.csv: {len(rows)}")
                
                # Check required columns
                if rows:
                    required_cols = ['ticket_number', 'client_name', 'reference', 
                                   'net_weight', 'rate', 'amount']
                    missing_cols = [col for col in required_cols if col not in rows[0]]
                    if missing_cols:
                        print(f"❌ Missing columns in merged.csv: {missing_cols}")
                        return False
            
            # Check each week
            stats = {
                'total_clients': set(),
                'total_tickets': 0,
                'total_images': 0,
                'total_amount': 0.0
            }
            
            for week_dir in set(d.split('/')[0] for d in week_dirs if '/' in d):
                print(f"\n📅 Checking {week_dir}:")
                
                # Check for manifest
                manifest_path = f"{week_dir}/manifest.csv"
                if manifest_path in namelist:
                    print("   ✅ Found manifest.csv")
                    
                    with zf.open(manifest_path) as f:
                        content = f.read().decode('utf-8')
                        # Extract totals from manifest
                        for line in content.split('\n'):
                            if line.startswith('Total Amount,'):
                                amount = float(line.split('$')[1])
                                stats['total_amount'] += amount
                
                # Check client directories
                client_dirs = [d for d in week_dirs if d.startswith(f"{week_dir}/client_")]
                client_names = set(d.split('/')[1] for d in client_dirs if len(d.split('/')) > 1)
                print(f"   ✅ Found {len(client_names)} clients")
                stats['total_clients'].update(client_names)
                
                # Check each client
                for client_dir in client_names:
                    client_path = f"{week_dir}/{client_dir}"
                    
                    # Check for invoice
                    invoice_path = f"{client_path}/invoice.csv"
                    if invoice_path in namelist:
                        print(f"   ✅ Found invoice for {client_dir}")
                        
                        with zf.open(invoice_path) as f:
                            content = f.read().decode('utf-8')
                            # Count tickets from invoice
                            for line in content.split('\n'):
                                if line.startswith('Total Tickets,'):
                                    count = int(line.split(',')[1])
                                    stats['total_tickets'] += count
                    
                    # Check for ticket images
                    image_files = [f for f in namelist if f.startswith(f"{client_path}/tickets/")]
                    if image_files:
                        print(f"   ✅ Found {len(image_files)} ticket images for {client_dir}")
                        stats['total_images'] += len(image_files)
                        
                        # Check image organization by reference
                        ref_dirs = set('/'.join(f.split('/')[:5]) for f in image_files if len(f.split('/')) > 4)
                        print(f"      - Images organized in {len(ref_dirs)} reference folders")
            
            # Print summary
            print(f"\n📊 Export Summary:")
            print(f"   - Total clients: {len(stats['total_clients'])}")
            print(f"   - Total tickets: {stats['total_tickets']}")
            print(f"   - Total images: {stats['total_images']}")
            print(f"   - Total amount: ${stats['total_amount']:.2f}")
            
            # Check for audit.json if there were issues
            if "audit.json" in namelist:
                print("\n⚠️  Found audit.json - checking for issues...")
                with zf.open("audit.json") as f:
                    audit = json.loads(f.read().decode('utf-8'))
                    if audit.get('validation', {}).get('validation_errors'):
                        print("   Validation errors recorded:")
                        for error in audit['validation']['validation_errors']:
                            print(f"   - {error}")
            
            return True
    
    def run_full_test(self, xls_path, pdf_path, date_str):
        """Run the complete E2E test"""
        print("🚀 Starting End-to-End Export Test")
        print("=" * 50)
        
        # Step 1: Login
        if not self.login():
            return False
        
        # Step 2: Upload files
        batch_id = self.upload_files(xls_path, pdf_path)
        if not batch_id:
            return False
        
        # Step 3: Process batch
        if not self.process_batch(batch_id):
            return False
        
        # Step 4: Validate export
        can_export = self.validate_export(date_str)
        if not can_export:
            print("⚠️  Validation failed, trying with force flag...")
            
        # Step 5: Create export
        zip_path = self.create_export(date_str, force=not can_export)
        if not zip_path:
            return False
        
        # Step 6: Validate ZIP structure
        if not self.validate_zip_structure(zip_path):
            return False
        
        print("\n✅ All tests passed!")
        print(f"📦 Export file: {zip_path}")
        return True


def main():
    parser = argparse.ArgumentParser(description='E2E test for weekly export system')
    parser.add_argument('xls_file', help='Path to XLS file')
    parser.add_argument('pdf_file', help='Path to PDF file')
    parser.add_argument('--date', default=date.today().isoformat(), 
                       help='Export date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--url', default='http://localhost:8000',
                       help='Base URL of the API')
    parser.add_argument('--username', default='admin',
                       help='Username for authentication')
    parser.add_argument('--password', default='admin',
                       help='Password for authentication')
    
    args = parser.parse_args()
    
    # Validate files exist
    if not os.path.exists(args.xls_file):
        print(f"❌ XLS file not found: {args.xls_file}")
        sys.exit(1)
    
    if not os.path.exists(args.pdf_file):
        print(f"❌ PDF file not found: {args.pdf_file}")
        sys.exit(1)
    
    # Run test
    tester = ExportE2ETest(args.url)
    success = tester.run_full_test(args.xls_file, args.pdf_file, args.date)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()