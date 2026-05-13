#!/usr/bin/env bash
# Download a few free portrait images from Pexels for testing UBIS matching.
# Use: ./scripts/download-sample-images.sh
# Images are saved to ./sample_test_images/ (create and use for New Case or Upload & match).

set -e
OUTDIR="${1:-sample_test_images}"
mkdir -p "$OUTDIR"

# Pexels free-to-use portrait photos (direct CDN URLs)
curl -sL -o "$OUTDIR/portrait-man-1.jpeg" "https://images.pexels.com/photos/2379004/pexels-photo-2379004.jpeg?auto=compress&cs=tinysrgb&w=600"
curl -sL -o "$OUTDIR/portrait-woman-1.jpeg" "https://images.pexels.com/photos/314548/pexels-photo-314548.jpeg?auto=compress&cs=tinysrgb&w=600"
curl -sL -o "$OUTDIR/portrait-woman-2.jpeg" "https://images.pexels.com/photos/2669601/pexels-photo-2669601.jpeg?auto=compress&cs=tinysrgb&w=600"

echo "Downloaded 3 sample images to $OUTDIR/"
echo "Use them in the app: New Case (face slots) or Matching → Upload & match."
