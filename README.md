# DPMB Trip Logger

A 24/7 vehicle trip logging system for Brno public transport (DPMB). Fetches real-time vehicle data from the IDSJMK API and logs all trip start/end events.

## Quick Start

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run the script
python trip_logger.py
```

### Deploy to Railway
1. Push code to GitHub
2. Go to [Railway.app](https://railway.app)
3. Create new project → Deploy from GitHub
4. Select this repository
5. Railway automatically deploys and runs 24/7

Logs will appear in the `logs/` directory organized by date.

## What It Logs

For each vehicle trip:
- **START**: When vehicle begins a route
- **END**: When vehicle stops/changes route
- **Timestamp**: Exact date and time
- **Vehicle ID**: Registration number
- **Course ID**: Route number (e.g., 00707)
- **Direction**: Direction of travel
- **Location**: GPS coordinates (when available)

### Example Log Output
```
logs/2026-04-12/
├── 00101.txt
├── 00707.txt
├── 00814.txt
└── ...
```

`00707.txt` contains:
```
2026-04-12 14:30:45 | START | Vehicle: 3601 | Direction: 1 | Location: 49.1912, 16.6127
2026-04-12 14:45:22 | END   | Vehicle: 3601 | Direction: 1
2026-04-12 14:46:10 | START | Vehicle: 3601 | Direction: 2 | Location: 49.1920, 16.6130
```

## File Structure
```
DPMB-bot/
├── trip_logger.py          # Main script
├── main.py                 # Discord bot (optional)
├── log.py                  # Utility functions
├── requirements.txt        # Dependencies
├── Procfile                # Railway configuration
├── DEPLOYMENT.md           # Detailed deployment guide
└── logs/                   # Generated log files
    ├── 2026-04-12/
    │   ├── 00101.txt
    │   └── ...
    └── veh/
```

## API Source
- **API**: https://mapa.idsjmk.cz/api/vehicles.json
- **Updates every**: 30 seconds (configurable)
- **Covers**: All DPMB public transport vehicles

## Configuration

Edit `trip_logger.py` to customize:
```python
FETCH_INTERVAL = 30         # Seconds between API calls
ACTIVITY_THRESHOLD = 300    # Seconds before marking inactive (5 min)
```

## GitHub Integration

Logs are automatically synced to GitHub:
- **Workflow**: `.github/workflows/sync-logs-to-github.yml`
- **Frequency**: Every hour
- **Action**: Commits log files to repository

To enable:
1. Create the `.github/workflows/` directory
2. Add the sync workflow (already included)
3. Logs will auto-commit hourly

## Troubleshooting

**Issue: "No logs appearing"**
- Check Railway logs: `railway logs`
- Verify internet connection
- Confirm API URL works: https://mapa.idsjmk.cz/api/vehicles.json

**Issue: "High memory/CPU usage"**
- Increase `FETCH_INTERVAL` (default 30s)
- Or decrease `ACTIVITY_THRESHOLD`

**Issue: "GitHub not syncing"**
- Check workflow in `.github/workflows/sync-logs-to-github.yml`
- Verify GitHub Actions is enabled in repo settings
- Check workflow runs tab for errors

## Performance
- Efficient async HTTP requests
- Minimal memory footprint (~50MB)
- Scales to thousands of vehicles
- Auto-recovery from API failures

## License & Attribution
- API provided by: IDSJMK (Integrovaný dopravní systém Jihomoravského kraje)
- Built for: DPMB (Dopravní podnik města Brna)

## Support
- For API issues: Check IDSJMK documentation
- For Railway: Visit https://railway.app/docs
- For this code: Check DEPLOYMENT.md
