# terraform/modules/s3/main.tf

# ── Audio Prompts Bucket ──────────────────────────────────────
resource "aws_s3_bucket" "audio_prompts" {
  bucket = "${var.name_prefix}-audio-prompts"
  tags   = { Name = "${var.name_prefix}-audio-prompts", Purpose = "IVR audio prompts" }
}

resource "aws_s3_bucket_versioning" "audio_prompts" {
  bucket = aws_s3_bucket.audio_prompts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audio_prompts" {
  bucket = aws_s3_bucket.audio_prompts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audio_prompts" {
  bucket                  = aws_s3_bucket.audio_prompts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Recordings Bucket ─────────────────────────────────────────
resource "aws_s3_bucket" "recordings" {
  bucket = "${var.name_prefix}-recordings"
  tags   = { Name = "${var.name_prefix}-recordings", Purpose = "Call recordings" }
}

resource "aws_s3_bucket_versioning" "recordings" {
  bucket = aws_s3_bucket.recordings.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "recordings" {
  bucket = aws_s3_bucket.recordings.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "recordings" {
  bucket                  = aws_s3_bucket.recordings.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    expiration {
      days = 365
    }
  }
}

# ── Lambda trigger notification ───────────────────────────────
resource "aws_s3_bucket_notification" "recordings_trigger" {
  bucket = aws_s3_bucket.recordings.id

  lambda_function {
    lambda_function_arn = var.recording_processor_arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "connect-recordings/"
    filter_suffix       = ".wav"
  }

  depends_on = [var.recording_processor_permission_id]
}
