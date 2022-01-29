#!C:\Python38\python.exe
from PIL import Image
import youtube_dl
import pytesseract
import cv2
import argparse
import numpy as np
import logging
from fuzzywuzzy import fuzz

#Returns string in the format of MM:SS
def formatSecondsToMinutes(seconds):
    return '{:02d}:{:02d}'.format(int(seconds / 60), int(seconds % 60))

# Print iterations progress
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

def preprocessImage(image):
    cv2img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv2img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=1.2, fy=1.2, interpolation=cv2.INTER_CUBIC)
    _, threshold = cv2.threshold(resized,130,255,cv2.THRESH_BINARY)
    return threshold

def cropImageToHeader(image): 
    width, height = image.size
    return image.crop((0, 0, width, height / 4))

#Runs pytesseract OCR on the image and returns the text parsed 
def getTextFromImage(image):
    return pytesseract.image_to_string(image, config='-c page_separator=""', lang=params.lang)

def getImageFromFrame(video, sec):
    video.set(cv2.CAP_PROP_POS_MSEC, sec*1000)
    hasFrame, image = video.read()

    if hasFrame:
        return Image.fromarray(image)
    else:
        return None

def parseFrame(video, sec):
    img = getImageFromFrame(video, sec)
    if img is None:
        return None
    else:
        preprocessed = preprocessImage(img)
        return getTextFromImage(preprocessed)

def fuzzyCompare(str1, str2):
    str1 = str1.replace("\n", " ")
    str2 = str2.replace("\n", " ")
    return fuzz.ratio(str1, str2)

#Called with video file and produces a txt file with the same name containing the video's text
def parseVideo(videoFilename, outputFilename):
    print(f'Beginning parse of {videoFilename} at {params.framerate} seconds between frames...')
    video = cv2.VideoCapture(videoFilename)

    maxFrames = params.limit
    if params.limit == -1:
        maxFrames = video.get(cv2.CAP_PROP_FRAME_COUNT) / (params.framerate * video.get(cv2.CAP_PROP_FPS)) + 1
    printProgressBar(0, maxFrames, prefix = f'Frame 1: ', suffix = 'Complete', length = 50)

    sec = 0
    count = 1
    lastFrameText = parseFrame(video, sec)

    with open(outputFilename, 'wb') as f:
        while lastFrameText is not None and (params.limit < 0 or count < params.limit):
            count = count + 1
            sec = round(sec + params.framerate, 2)
            frameText = parseFrame(video, sec)
            
            if frameText is None:
                break

            header = frameText.split("\n")[0]

            printProgressBar(count, maxFrames, prefix = f'Frame {count}', suffix = f'Header: {header}', length = 50)
            logging.info(f'Parsing frame {count} at {formatSecondsToMinutes(sec)} with header: {header}')

            ratio = fuzzyCompare(lastFrameText, frameText)

            if ratio > 90:
                logging.info('Found same content as last frame, skipping...')
                continue
            elif ratio < 30:
                #check if their headers are the same and check the length to make sure its adding, not removing content
                if fuzzyCompare(header, lastFrameText.split("\n")[0]) > 90 and len(frameText) > len(lastFrameText):
                    logging.info('Updating frame content...')
                else:
                    logging.info('Found new content, writing last frame to file')
                    f.write(lastFrameText.encode('utf-8'))

            lastFrameText = frameText

        if lastFrameText is not None:
            f.write(lastFrameText.encode('utf-8'))
    print('\n' + f'{count} frames processed from {videoFilename}')
    print(f'OCR results written to {outputFilename}')

#Called when downloadVideo() finishes and starts parsing the video file
def parseHook(status):
    if status['status'] == 'finished':
        parseVideo(status['filename'], status['filename'].split('.')[0] + '.txt')

#Utilizes youtube_dl to download the url provided into mp4 format to local directory
def downloadVideo(videoUrl):
    ydl_opts = {
        'format': '135', # 854 x 480
        'outtmpl': '%(title)s.mp4',
        'progress_hooks': [parseHook],
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([videoUrl])

def main():
    parser = argparse.ArgumentParser(description='Parse a video for text and write it to a file')
    parser.add_argument('Video', metavar='video', help='the path or link to the video file')
    parser.add_argument('--dl', action='store_true', help='download the video from the link provided')
    parser.add_argument('-f', '--framerate', default=5, type=float, help='define the seconds between frames (default=5)')
    parser.add_argument('-l', '--limit', default=-1, type=float, help='define the max number of frames to read (default=-1)')
    parser.add_argument('--lang', default='eng', help='the language in the video')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose output')
    global params
    params = parser.parse_args()

    if params.verbose:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
        
    if params.dl:
        downloadVideo(params.Video)
    else:
        parseVideo(params.Video, params.Video.split('.')[0] + '.txt')


if __name__ == "__main__":
    main()