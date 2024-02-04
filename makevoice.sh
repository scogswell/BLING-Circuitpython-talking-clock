#!/bin/sh
# For making voice samples for circuitpython BLING talking clock
# Runs on Mac OSX.  
# Requires ffmpeg.  
VOICE="Tessa"
DIR="voice"
FFMPEG_OPTS="-nostats -hide_banner -loglevel error"
WAV_OPTS="-f wav -bitexact -acodec pcm_s16le -ac 1 -ar 22050"

echo "voice $VOICE"
for t in `seq 1 59`
do
	echo "Generating $t"
	say -v $VOICE $t --file-format AIFF -o "$DIR/$t"
	echo " ... convert to wav"
	`ffmpeg $FFMPEG_OPTS -y -i "$DIR/$t.aiff" $WAV_OPTS "$DIR/$t.wav"`
	echo " ... remove file"
	`rm "$DIR/$t.aiff"`
	echo " ... done"
done

TEXT="oh"
FILE="0"
say -v $VOICE $TEXT --file-format AIFF -o "$DIR/$FILE"
ffmpeg $FFMPEG_OPTS -y -i "$DIR/$FILE.aiff" $WAV_OPTS "$DIR/$FILE.wav"
`rm "$DIR/$FILE.aiff"`

TEXT="ay m"
FILE="am"
say -v $VOICE $TEXT --file-format AIFF -o "$DIR/$FILE"
ffmpeg $FFMPEG_OPTS -y -i "$DIR/$FILE.aiff" $WAV_OPTS "$DIR/$FILE.wav"
`rm "$DIR/$FILE.aiff"`

TEXT="p m"
FILE="pm"
say -v $VOICE $TEXT --file-format AIFF -o "$DIR/$FILE"
ffmpeg $FFMPEG_OPTS -y -i "$DIR/$FILE.aiff" $WAV_OPTS "$DIR/$FILE.wav"
`rm "$DIR/$FILE.aiff"`

TEXT="hundred"
FILE="hundred"
say -v $VOICE $TEXT --file-format AIFF -o "$DIR/$FILE"
ffmpeg $FFMPEG_OPTS -y -i "$DIR/$FILE.aiff" $WAV_OPTS "$DIR/$FILE.wav"
`rm "$DIR/$FILE.aiff"`

TEXT="bling"
FILE="bling"
say -v $VOICE $TEXT --file-format AIFF -o "$DIR/$FILE"
ffmpeg $FFMPEG_OPTS -y -i "$DIR/$FILE.aiff" $WAV_OPTS "$DIR/$FILE.wav"
`rm "$DIR/$FILE.aiff"`


