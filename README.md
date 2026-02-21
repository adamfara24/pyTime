# pyTime

A text-based Python CLI tool for uploading, downloading, and sharing files and directories via AWS S3.

---

## AWS Setup Guide

### 1. Create an AWS Account

1. Go to [https://aws.amazon.com](https://aws.amazon.com) and click **Create an AWS Account**
2. Follow the sign-up steps (you'll need a credit card — S3 usage at small scale is covered by the free tier)
3. Sign in to the **AWS Management Console**

---

### 2. Create an IAM User with S3-Only Permissions

Creating a dedicated IAM user (instead of using your root account) is the secure way to grant programmatic access.

1. In the AWS Console, search for **IAM** and open it
2. Click **Users** → **Create user**
3. Give it a name (e.g. `pytime-user`) and click **Next**
4. Select **Attach policies directly**
5. Click **Create policy** (opens a new tab):
   - Select the **JSON** tab and paste the policy below
   - Replace `YOUR-BUCKET-NAME` with whatever you plan to name your S3 bucket (e.g. `pytime-files`)
   - Click **Next**, name it `PyTimeS3Policy`, then **Create policy**
6. Back on the user creation tab, refresh and search for `PyTimeS3Policy`, select it, and click **Next** → **Create user**

**IAM Policy JSON:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:HeadBucket",
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR-BUCKET-NAME",
        "arn:aws:s3:::YOUR-BUCKET-NAME/*"
      ]
    }
  ]
}
```

---

### 3. Generate Access Keys

1. Open the IAM user you just created
2. Go to the **Security credentials** tab
3. Under **Access keys**, click **Create access key**
4. Select **Command Line Interface (CLI)** as the use case
5. Click through and **download the CSV** or copy both values:
   - **Access Key ID** (starts with `AKIA...`)
   - **Secret Access Key** (only shown once — save it!)

---

## Installation

```bash
# Clone the repo
git clone https://github.com/adamfara24/pyTime.git
cd pyTime

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Running pyTime

```bash
python main.py
```

On first run, you'll be prompted to enter your AWS credentials and preferred bucket name. These are saved to `~/.pytime/config.json` for future sessions.

Every launch will prompt for your username, which is used to namespace your files in S3 (e.g. `alice/my-folder/file.txt`).

---

## Project Structure

```
pyTime/
├── main.py           # Entry point
├── config.py         # Credential config and first-run setup
├── requirements.txt
├── README.md
├── storage/
│   └── s3_client.py  # S3 connection and bucket management
└── ui/
    ├── menu.py       # Interactive main menu
    └── prompts.py    # Reusable input prompts
```
