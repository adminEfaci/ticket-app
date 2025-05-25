#!/bin/bash
curl -X POST http://localhost:8000/upload/pairs \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3MGJhMDk4Yy1hZDIwLTQ5MDctYmQyMC0zMGMzNDQ3NDQzYTYiLCJlbWFpbCI6ImFkbWluQGV4YW1wbGUuY29tIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzQ4MjA3OTc1fQ.vibP0SxGEfpZSMKunReakSWcYOJXiZs_DatOkDO19ak" \
  -F "files=@samples/APRIL_14_2025.xls" \
  -F "files=@samples/APRIL_14_2025.pdf" \
  -F "client_id=test-client" \
  -F "description=Test upload"