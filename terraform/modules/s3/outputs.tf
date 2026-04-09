output "audio_prompts_bucket_name" { value = aws_s3_bucket.audio_prompts.bucket }
output "recordings_bucket_name"    { value = aws_s3_bucket.recordings.bucket }
output "audio_prompts_bucket_arn"  { value = aws_s3_bucket.audio_prompts.arn }
output "recordings_bucket_arn"     { value = aws_s3_bucket.recordings.arn }
