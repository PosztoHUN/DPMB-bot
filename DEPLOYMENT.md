# Trip Logger - Railway 24/7 Deployment Guide

## Overview
This script logs all vehicle trips from the IDSJMK API (Brno public transport). It tracks when vehicles start and end their routes, logging timestamps and trip information.

## Features
- ✅ 24/7 operation on Railway platform
- ✅ Asynchronous API fetching (efficient resource usage)
- ✅ Automatic trip start/end detection
- ✅ Organized logs by date and course ID
- ✅ Error handling and recovery
- ✅ Detailed logging for monitoring

## File Structure
```
logs/
├── YYYY-MM-DD/          # Daily log directories
│   ├── 00101.txt        # Logs for course 00101
│   ├── 00707.txt        # Logs for course 00707
│   └── ...
└── veh/                 # Vehicle-specific logs (if needed)

trip_logger.py           # Main logging script
requirements.txt         # Python dependencies
Procfile                 # Railway process configuration
```

## Deployment on Railway

### 1. Prerequisites
- Railway account (https://railway.app)
- GitHub repository with this code

### 2. Create Railway Project
1. Go to Railway.app → New Project
2. Select "Deploy from GitHub repository"
3. Connect your GitHub repository
4. Allow Railway to access your repo

### 3. Configure Environment Variables
In Railway project settings, no specific environment variables are required, but you can set:
- `LOG_LEVEL=INFO` (or DEBUG for more verbose logging)
- `FETCH_INTERVAL=30` (seconds between API calls)
- `ACTIVITY_THRESHOLD=300` (seconds before marking vehicle inactive)

### 4. Deploy
Railway will automatically:
1. Install dependencies from requirements.txt
2. Run the Procfile command
3. Keep the service running 24/7

## Log File Format
Each log file (e.g., `logs/2026-04-12/00707.txt`) contains entries like:
```
2026-04-12 14:30:45 | START | Vehicle: 1234 | Direction: 1 | Location: 49.1912, 16.6127
2026-04-12 14:45:22 | END   | Vehicle: 1234 | Direction: 1
2026-04-12 14:46:10 | START | Vehicle: 1234 | Direction: 2 | Location: 49.1920, 16.6130
```

## GitHub Integration
Logs are stored locally in the `logs/` directory. To sync with GitHub:

### Option 1: Auto-commit logs periodically
Add a scheduled workflow in `.github/workflows/sync-logs.yml`:
```yaml
name: Sync Logs to GitHub
on:
  schedule:
    - cron: '0 * * * *'  # Every hour
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Sync logs
        run: |
          git config --local user.email "bot@railway.app"
          git config --local user.name "Log Bot"
          git add logs/
          git commit -m "Auto: Update logs $(date)"
          git push
```

### Option 2: Manual sync
SSH into Railway container or use Railway CLI to pull logs

### Option 3: Connect to external storage
- Use Railway PostgreSQL for structured logging
- Use AWS S3 for backup
- Set up webhook to POST logs to external service

## Monitoring

### View logs in Railway
```bash
railway logs
```

### Check active vehicles
Logs show all vehicle movements in real-time

### Error handling
- Max 10 consecutive API errors before restart
- Automatic recovery on timeout
- Detailed error logging

## Configuration Options

Edit `trip_logger.py` to adjust:
- `FETCH_INTERVAL` (line 17): How often to fetch API (default: 30 seconds)
- `ACTIVITY_THRESHOLD` (line 18): When to mark vehicle inactive (default: 300 seconds)
- `API_URL` (line 16): API endpoint

## Troubleshooting

### "ModuleNotFoundError: No module named 'aiohttp'"
Make sure requirements.txt is up to date: `pip install -r requirements.txt`

### Logs not appearing
1. Check Railway logs: `railway logs`
2. Verify API_URL is accessible
3. Check file permissions on logs directory

### High memory usage
Reduce `FETCH_INTERVAL` or adjust `ACTIVITY_THRESHOLD`

## API Response Format
The script expects JSON with vehicle objects containing:
- `Registration` or `id`: Vehicle identifier
- `Course` or `route`: Course/route ID
- `Direction`: Direction identifier
- `Latitude`, `Longitude`: GPS coordinates (optional)

## Support
For issues or questions about the IDSJMK API:
- Visit: https://mapa.idsjmk.cz
- Check API documentation
