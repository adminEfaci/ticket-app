# Weekly Export System Documentation

## Overview

The Weekly Export System processes ticket data from XLS and PDF files, groups them by week/client/reference, and generates comprehensive billing exports with the following features:

- **Automatic ticket grouping** by week (Monday-Saturday)
- **Client-based invoicing** with reference-level detail
- **Image extraction and organization** by ticket number
- **Financial validation** with 2-decimal precision
- **Comprehensive audit logging** for compliance

## Export Structure

```
invoices_export.zip
├── merged.csv                    # All REPRINT tickets with billing info
├── week_2024-04-15/             # Week directory (Monday date)
│   ├── manifest.csv             # Weekly summary of all clients
│   ├── client_Client_007/       # Client directory
│   │   ├── invoice.csv          # Client invoice grouped by reference
│   │   └── tickets/             # Ticket images
│   │       ├── #007/           # Reference folder
│   │       │   ├── 4121.png    # Ticket images named by number
│   │       │   └── 4122.png
│   │       └── MM1001/
│   │           └── 4123.png
│   └── client_Client_004/
│       └── ...
├── week_2024-04-22/
│   └── ...
└── audit.json                   # (Optional) Validation errors/warnings
```

## API Endpoints

### 1. Validate Export Data
```bash
POST /api/export/validate
{
    "start_date": "2024-04-15",
    "end_date": "2024-04-30",    # Optional
    "export_type": "weekly",
    "include_images": true,
    "client_ids": ["uuid1", "uuid2"]  # Optional filter
}
```

### 2. Create Export Bundle
```bash
POST /api/export/invoices-bundle
{
    "start_date": "2024-04-15",
    "end_date": "2024-04-30",
    "export_type": "weekly",
    "include_images": true,
    "force_export": false         # Override validation failures
}
```

### 3. Quick Weekly Export
```bash
GET /api/export/invoices-bundle/2024-04-15?include_images=true&force=false
```

### 4. Download Previous Export
```bash
GET /api/export/download/{export_id}
```

## CLI Usage

### Basic E2E Test
```bash
python test_export_e2e.py april14.xls april14.pdf --date 2024-04-15
```

### Full Command Example
```bash
# Upload and process files
curl -F "xls=@april14.xls" -F "pdf=@april14.pdf" \
     -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/upload-batch

# Process the batch
curl -X POST -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/batch/{batch_id}/process

# Create and download export
curl -H "Authorization: Bearer $TOKEN" \
     -o invoices_export.zip \
     http://localhost:8000/api/export/invoices-bundle/2024-04-15

# Extract and verify
unzip invoices_export.zip && tree
```

## Validation Rules

### Critical Validations (Block Export)
- ✅ XLS ticket count must match PDF image count (1:1 for REPRINT tickets)
- ✅ Each ticket must have `image_path` pointing to extracted image
- ✅ No duplicate ticket numbers allowed
- ✅ All tickets must have valid `entry_date`
- ✅ All tickets must be assigned to a client with an active rate

### Financial Validations
- ✅ `net_weight * rate = amount` (rounded to 2 decimals)
- ✅ Invoice line item totals must match reference group totals
- ✅ Client invoice totals must match sum of line items
- ✅ Weekly manifest totals must match sum of client totals

### Data Integrity
- ✅ Only REPRINT tickets are included (VOID/ORIGINAL excluded)
- ✅ Only billable tickets are exported
- ✅ Week ranges are Monday-Saturday only
- ✅ All weights and amounts rounded to 2 decimal places

## File Formats

### merged.csv
```csv
week_start,client_id,client_name,reference,ticket_number,entry_date,net_weight,rate,amount,note
2024-04-15,uuid,Client 007,#007,T4121,2024-04-15,8.50,25.00,212.50,Note text
```

### invoice.csv
```
INVOICE
Client: Client 007
Client ID: uuid
Period: 2024-04-15 to 2024-04-20
Invoice Date: 2024-04-23

Reference,Tickets,Weight (tonnes),Rate,Amount
#007,3,27.00,$25.00,$675.00
MM1001,1,12.00,$25.00,$300.00

Total Tickets,4
Total Weight,39.00 tonnes
Total Amount,$975.00
```

### manifest.csv
```
WEEKLY MANIFEST
Week: 2024-04-15 to 2024-04-20
Generated: 2024-04-23T10:30:00

Client ID,Client Name,Tickets,References,Weight (tonnes),Rate,Total Amount
uuid1,Client 007,4,2,39.00,$25.00,$975.00
uuid2,Client 004,2,1,22.00,$30.00,$660.00

Total Clients,2
Total Tickets,6
Total Weight,61.00 tonnes
Total Amount,$1635.00
```

## Testing

### Unit Tests
```bash
pytest backend/tests/unit/test_weekly_export_service.py -v
pytest backend/tests/unit/test_invoice_generator_service.py -v
```

### Integration Tests
```bash
pytest backend/tests/integration/test_export_flow.py -v
```

### E2E Test Script
```bash
# Basic test
python test_export_e2e.py test_files/april14.xls test_files/april14.pdf

# With custom date
python test_export_e2e.py files.xls files.pdf --date 2024-04-15

# Against staging
python test_export_e2e.py files.xls files.pdf --url https://staging.example.com
```

## Error Handling

### Validation Errors
- Missing images: Use `force_export=true` to proceed
- Duplicate tickets: Review and clean data or use force flag
- Missing rates: Ensure all clients have active rates for the period

### Audit Trail
All exports generate an audit log entry with:
- User who initiated export
- Timestamp and date range
- Validation status and any errors
- Total tickets, clients, and amounts
- File path of generated export

### Export Failures
Check `ExportAuditLog` table for:
- `status`: success, failed, or partial
- `validation_errors`: JSON array of specific issues
- `export_metadata`: Detailed export information

## Performance Considerations

- Exports are generated on-demand (not cached)
- Large exports (>1000 tickets) may take 10-30 seconds
- Image copying is the slowest operation
- Consider `include_images=false` for faster exports

## Security

- Only ADMIN and MANAGER roles can create exports
- VIEWER role can download existing exports
- All exports are logged with user attribution
- Sensitive data is never logged in plain text