#!/usr/bin/env bash
# Build the minimal LGPL ffmpeg that Speaker Scribe bundles.
#
# The stock Homebrew build is configured --enable-gpl, so shipping it inside an
# MIT application would put the whole bundle under the GPL. This project only
# ever decodes audio to 16 kHz mono PCM, and every decoder needed for that is
# LGPL, so --disable-gpl costs nothing.
#
# Everything else is switched off. The result does one job, is a few megabytes
# rather than eighty, and its licence is unambiguous.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${FFMPEG_VERSION:-7.1.1}"
SRC="$ROOT/build/ffmpeg-src/ffmpeg-${VERSION}"
OUT="$ROOT/build/ffmpeg"

[ -d "$SRC" ] || {
  echo "Source not found at $SRC" >&2
  echo "curl -sL -o build/ffmpeg-src/ffmpeg.tar.xz https://ffmpeg.org/releases/ffmpeg-${VERSION}.tar.xz" >&2
  echo "tar -xf build/ffmpeg-src/ffmpeg.tar.xz -C build/ffmpeg-src" >&2
  exit 1
}

cd "$SRC"

echo "==> Configuring a decode-only LGPL build"
./configure \
  --prefix="$OUT" \
  --disable-gpl --disable-nonfree --disable-version3 \
  --disable-everything --disable-doc --disable-network --disable-autodetect \
  --disable-shared --enable-static \
  --disable-ffplay --disable-ffprobe --disable-avdevice --disable-postproc \
  --enable-decoder=aac,aac_latm,alac,flac,mp3,mp3float,opus,vorbis,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le,pcm_u8,pcm_mulaw,pcm_alaw \
  --enable-demuxer=aac,flac,mov,mp3,ogg,wav,w64,caf,aiff,matroska \
  --enable-parser=aac,aac_latm,flac,mpegaudio,opus,vorbis \
  --enable-encoder=pcm_s16le \
  --enable-muxer=pcm_s16le,wav \
  --enable-protocol=file,pipe \
  --enable-filter=aresample,aformat,anull,atrim \
  --enable-swresample \
  >/dev/null

echo "==> Building"
make -j"$(sysctl -n hw.ncpu)" >/dev/null
make install >/dev/null

BIN="$OUT/bin/ffmpeg"
echo
echo "Built $BIN"
ls -lh "$BIN" | awk '{print "  size: " $5}'
"$BIN" -hide_banner -version | head -2 | sed 's/^/  /'
echo
echo "  GPL flags present (should be empty):"
"$BIN" -hide_banner -version | grep -o -- "--enable-gpl\|--enable-nonfree\|--enable-version3" | sed 's/^/    /' || echo "    none"
