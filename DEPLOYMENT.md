# Hugging Face Spaces Deployment Guide

This project is configured for deployment on **Hugging Face Spaces** using the **Docker SDK**.

## Prerequisites

1.  A [Hugging Face Account](https://huggingface.co/join).
2.  [Git](https://git-scm.com/downloads) installed on your machine.

---

## 1. Create a New Space

1.  Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2.  **Space Name**: `rmbg-studio` (or your preferred name).
3.  **License**: `MIT`.
4.  **SDK**: Select **Docker** (This is crucial!).
5.  **Hardware**: `CPU basic` (Free) is sufficient, though `CPU upgrade` or `T4 small` will be faster.
6.  **Visibility**: Public or Private.
7.  Click **Create Space**.

---

## 2. Connect and Push Code

Open your terminal in the project folder and run these commands (replace `YOUR_USERNAME` with your HF username):

```bash
# 1. Initialize Git (if not already done)
git init

# 2. Add the Hugging Face remote
git remote add origin https://huggingface.co/spaces/YOUR_USERNAME/rmbg-studio

# 3. Add all files
git add .
git add -f Dockerfile 

# 4. Commit
git commit -m "Initial commit"

# 5. Push to deploy
git push -u origin main
```

**Note:** If you get an error about "unrelated histories", use `git push -f origin main` to force overwrite the initial empty repo.

---

## 3. Important Configurations

### Binary Files (Images/Icons)
Hugging Face prohibits pushing large binary files (like images) directly to git without LFS. To avoid errors, this project's `.gitignore` excludes:
- `*.png`, `*.jpg`, `*.jpeg`
- `icon.png`
- `screenshots/`

If you *need* to upload these, you must set up [Git LFS](https://git-lfs.com/) first.

### Dependencies (`Dockerfile`)
The included `Dockerfile` is optimized for Spaces:
- Base Image: `python:3.10-slim`
- System Libs: `libgl1`, `libglib2.0-0` (required for OpenCV)
- User: Runs as non-root user `user` (ID 1000) for security.
- Output: Creates `/app/output_images` with correct permissions.

---

## 4. Updates & Troubleshooting

### How to Update
Whenever you make code changes:
```bash
git add .
git commit -m "Describe your changes"
git push
```
The Space will automatically rebuild and restart.

### Common Errors

**Error: `libgl1-mesa-glx` not found**
- **Cause**: Deprecated package in newer Debian versions.
- **Fix**: Use `libgl1` instead. (Already fixed in current `Dockerfile`).

**Error: Push rejected (binary files)**
- **Cause**: Trying to upload images without LFS.
- **Fix**: Run `git rm --cached icon.png` (and other images) to stop tracking them, then commit and push.

**Error: Application Error / Build Failed**
- Go to your Space's **Logs** tab to see the detailed error message. most issues are missing `requirements.txt` packages or path issues.
