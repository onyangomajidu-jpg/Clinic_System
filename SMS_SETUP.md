# SMS Reminders Setup Guide

This guide explains how to configure and enable SMS appointment reminders for patients.

## Current Status

The SMS reminder system is **currently in simulated mode**. This means:
- SMS messages are logged but not actually sent
- The system tracks what would be sent for testing purposes
- This is intentional for development and testing without API costs

## To Enable Real SMS Sending

### Step 1: Get Africa's Talking Account

1. Go to [https://africastalking.com](https://africastalking.com)
2. Sign up for a free account
3. Verify your account
4. Navigate to **Dashboard → Settings → API Key**
5. Copy your:
   - **Username** (usually your phone number or email)
   - **API Key**

### Step 2: Configure Environment Variables

Edit the `.env` file in the `Clinic_System` directory:

```bash
# Add these lines (replace with your actual credentials)
AT_API_KEY=your_actual_api_key_here
AT_USERNAME=your_actual_username_here
```

**Example:**
```bash
AT_API_KEY=abc123def456ghi789jkl012mno345pqr678stu
AT_USERNAME=+256712345678
```

### Step 3: Install Africa's Talking SDK

Run the following command:

```bash
cd Clinic_System
.venv\Scripts\pip.exe install africastalking
```

Or install from requirements.txt:

```bash
cd Clinic_System
.venv\Scripts\pip.exe install -r requirements.txt
```

### Step 4: Restart the Server

```bash
# Stop the current server
Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*manage.py runserver*"} | Stop-Process -Force

# Start it again
cd Clinic_System
.venv\Scripts\python.exe manage.py runserver 8000
```

## Testing SMS Reminders

### Option A: Test via Django Admin

1. Go to `http://localhost:8000/admin/`
2. Navigate to **Core → Appointments**
3. Create or edit an appointment
4. Click **"Send SMS reminder"** button
5. Check the **SMS Reminders** section to see if it was sent

### Option B: Use Management Command

Send reminders for appointments in the next 24 hours:

```bash
cd Clinic_System
.venv\Scripts\python.exe manage.py send_reminders --days 1
```

Send reminders for appointments in the next 7 days:

```bash
cd Clinic_System
.venv\Scripts\python.exe manage.py send_reminders --days 7
```

**Dry run** (see what would be sent without actually sending):

```bash
cd Clinic_System
.venv\Scripts\python.exe manage.py send_reminders --days 1 --dry-run
```

### Option C: Automatic Scheduling (Production)

For production use, schedule the command to run automatically:

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create Basic Task → "Send SMS Reminders"
3. Trigger: Daily at 8:00 AM
4. Action: Start a program
5. Program: `D:\project\clinic_system\Clinic_System\.venv\Scripts\python.exe`
6. Arguments: `manage.py send_reminders --days 1`
7. Start in: `D:\project\clinic_system\Clinic_System`

**Linux/Mac (Cron):**
```bash
# Add to crontab (crontab -e)
0 8 * * * cd /path/to/Clinic_System && .venv/bin/python manage.py send_reminders --days 1
```

## Monitoring SMS Status

### View SMS Reminder Logs

1. Go to `http://localhost:8000/admin/`
2. Navigate to **Core → SMS Reminders**
3. You'll see:
   - **Status**: "sent", "failed", or "pending"
   - **Phone Number**: Where the SMS was sent
   - **Message**: The actual message content
   - **Provider Message ID**: Africa's Talking confirmation
   - **Error Message**: If sending failed

### Check Recent Reminders Dashboard

1. Go to `http://localhost:8000/accounts/dashboard/`
2. View **Appointment Dashboard**
3. See reminder statistics:
   - Reminders sent today
   - Upcoming appointments
   - Recent reminder history

## Common Issues

### Issue 1: "africastalking package not installed"

**Solution:**
```bash
cd Clinic_System
.venv\Scripts\pip.exe install africastalking
```

### Issue 2: "SMS simulated" in logs

**Cause:** API credentials not configured

**Solution:** Add `AT_API_KEY` and `AT_USERNAME` to `.env` file

### Issue 3: "No phone number" errors

**Cause:** Patient doesn't have a phone number recorded

**Solution:** Edit the patient record and add their phone number

### Issue 4: SMS sent but not received

**Possible causes:**
- Patient's phone is off or out of coverage
- Wrong phone number format (use format: `+256712345678` for Uganda)
- Africa's Talking account not funded (check balance)
- Phone number is on Do Not Disturb (DND) list

## Phone Number Format

Use **E.164 format** for best results:
- Uganda: `+256712345678`
- Kenya: `+254712345678`
- Tanzania: `+255712345678`

## Costs

- Africa's Talking charges per SMS sent
- Typical rates: UGX 25-50 per SMS in Uganda
- Monitor your usage at [https://account.africastalking.com](https://account.africastalking.com)

## Support

For Africa's Talking API issues:
- Documentation: [https://docs.africastalking.com](https://docs.africastalking.com)
- Support: support@africastalking.com

For clinic system issues:
- Check logs in `server.log` and `server_err.log`
- Review SMSReminder records in admin panel
