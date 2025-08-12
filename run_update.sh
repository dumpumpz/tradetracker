#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- STARTING AUTOMATED UPDATE SCRIPT ---"

# --- 1. Configure Git ---
# Use the GitHub Actions bot user for the commit
echo "Configuring Git user..."
git config --global user.name "github-actions[bot]"
git config --global user.email "github-actions[bot]@users.noreply.github.com"

# --- 2. Run Python Scripts ---
# These scripts will generate the .json and .png files
echo "Running Python analysis and charting scripts..."
python3 generate_accurate_ma.py
python3 sr_levels_analysis.py
python3 generate_charts.py

# --- 3. Commit and Push Changes ---
echo "Checking for changes..."
# Use 'git status --porcelain' to see if there are any changes
if [[ -n $(git status --porcelain) ]]; then
  echo "Changes found. Committing and pushing..."
  git add ma_analysis.json sr_levels_analysis.json market_opens.json charts/
  git commit -m "Automated analysis data and chart update"
  git push
  echo "Push complete."
else
  echo "No changes to commit."
fi

echo "--- SCRIPT FINISHED SUCCESSFULLY ---"
