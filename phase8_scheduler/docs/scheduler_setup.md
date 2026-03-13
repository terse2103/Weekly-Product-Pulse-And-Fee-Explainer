# Scheduler Setup Guide

## Overview
This pipeline is automated using GitHub Actions. It runs every Sunday at 4:00 AM UTC (9:30 AM IST).
It uses the `.github/workflows/weekly_pulse.yml` workflow file.

## Prerequisites
To run the automated pipeline, you need to configure Secrets in your GitHub repository.

### GitHub Actions Secrets
1. Go to your repository **Settings** > **Secrets and variables** > **Actions**.
2. Click **New repository secret**.
3. Add the following secrets:
   - `GROQ_API_KEY`: Your Groq API key for LLaMA 3.3 70B inference.
   - `GMAIL_CREDENTIALS`: Optional. Follow the Phase 7 Email setup to obtain this if using Gmail API.

### Repository Permissions
To allow the GitHub Actions bot to commit the generated outputs back to the repository:
1. Go to **Settings** > **Actions** > **General**.
2. Scroll down to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

## Manual Trigger
You can also manually trigger the pipeline:
1. Go to the **Actions** tab in your GitHub repository.
2. Select **Weekly Product Pulse** on the left sidebar.
3. Click the **Run workflow** dropdown and run it from the main branch.
