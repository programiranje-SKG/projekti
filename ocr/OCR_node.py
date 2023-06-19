#!/usr/bin/env python
from __future__ import print_function

import roslib
# roslib.load_manifest('exercise4')
import sys
import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image
from cv_bridge import *
# from std_msgs.msg import ColorRGBA
import pytesseract
from task2.msg import digits
from joblib import load
import os
from OCR_learning import PCA_learner

dictm = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

# The object that we will pass to the markerDetect function

params = cv2.aruco.DetectorParameters_create()
"""
print("aruco params for circle detection")
print("params.adaptiveThreshConstant: {}".format(params.adaptiveThreshConstant))
print("params.adaptiveThreshWinSizeMax: {}".format(params.adaptiveThreshWinSizeMax))
print("params.adaptiveThreshWinSizeMin: {}".format(params.adaptiveThreshWinSizeMi))
print("params.minCornerDistanceRate: {}".format(params.minCornerDistanceRate))
print("params.adaptiveThreshWinSizeStep: {}".format(params.adaptiveThreshWinSizeStep))

print(params.adaptiveThreshConstant)
print(params.adaptiveThreshWinSizeMax)
print(params.adaptiveThreshWinSizeMin)
print(params.minCornerDistanceRate)
print(params.adaptiveThreshWinSizeStep)
"""

# To see description of the parameters
# https://docs.opencv.org/3.3.1/d1/dcd/structcv_1_1aruco_1_1DetectorParameters.html

# You can set these parameters to get better marker detections
params.adaptiveThreshConstant = 25
adaptiveThreshWinSizeStep = 2

counter = 0


class The_Rectifier:
    def __init__(self):
        rospy.init_node('image_converter', anonymous=True)

        # An object we use for converting images between ROS format and OpenCV format
        self.bridge = CvBridge()

        # Subscribe to the image and/or depth topic
        self.image_sub = rospy.Subscriber("/camera/rgb/image_color", Image, self.image_callback)

        self.pub = rospy.Publisher('/task2/digits', digits, queue_size=10)

    def image_callback(self, data):
        # print('Iam here!')

        try:
            # Todo is it dangerous? can we have image from previous ring?
            self.cv_image = self.bridge.imgmsg_to_cv2(data, "bgr8")
            self.timestamp = data.header.stamp
            self.service_OCR_handle()
        except CvBridgeError as e:
            print(e)

    def mock_image_callback(self, path):
        """
        function mocks image callback by loading image from path
        """

        # Create a blank 640x480 black image
        img = np.zeros((480, 640, 3), np.uint8)
        # Fill image with color(set each pixel to some gray color)
        img[:] = (167, 152, 139)

        # convert image to 640 x 480
        img_input = cv2.imread(path, cv2.IMREAD_COLOR)
        # print(img_input.shape)
        img_input = cv2.resize(img_input, (318, 450))
        # fill with mock image
        img[15:465, 161:479] = img_input

        cv2.imshow('OCR image', img)
        cv2.waitKey(30)

        self.cv_image = img
        self.timestamp = rospy.Time.now()

        self.service_OCR_handle()

    def service_OCR_handle(self):
        print("--------------------------")
        print("OCR node")

        cv_image = self.cv_image

        # Set the dimensions of the image
        self.dims = cv_image.shape

        # Tranform image to gayscale
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        # cv2.imshow('gray', gray)
        # cv2.waitKey(1)

        # Do histogram equlization
        img_hist = cv2.equalizeHist(gray)

        # cv2.imshow('histogram', img_hist)
        # cv2.waitKey(1)

        # Binarize the image
        # ret, thresh = cv2.threshold(img_hist, 50, 255, 0)
        thresh_countours = cv2.adaptiveThreshold(img_hist, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11,
                                                 5)

        # cv2.imshow('thresh_countours', thresh_countours)
        # cv2.waitKey(4000)

        # cv2.imshow('thresh', thresh)
        # cv2.waitKey(4000)

        # Extract contours
        _, contours, hierarchy = cv2.findContours(thresh_countours, 2, 2)

        # Example how to draw the contours
        # cv2.drawContours(img, contours, -1, (255, 0, 0), 3)

        # Fit elipses to all extracted contours
        elps = []
        for cnt in contours:
            #     print cnt
            #     print cnt.shape
            if cnt.shape[0] >= 40:
                ellipse = cv2.fitEllipse(cnt)
                elps.append(ellipse)

        # Find two elipses with same centers
        candidates = []
        for n in range(len(elps)):
            for m in range(n + 1, len(elps)):
                e1 = elps[n]
                e2 = elps[m]
                dist = np.sqrt(((e1[0][0] - e2[0][0]) ** 2 + (e1[0][1] - e2[0][1]) ** 2))
                #             print dist
                if dist < 5:
                    candidates.append((e1, e2))

        ###########################################
        #### THIS IS THE CODE THAT IT IS RELEVANT TO YOU
        #### IT SHOULD BE INCLUDED IN YOUR OWN FUNCTION FOR RING DETECTION
        ###########################################

        if len(candidates) > 0:
            # x_mean = np.array([np.array(candidates[0][0][0]), np.array(candidates[0][0][1])]).mean(0)[0]
            img_width = self.dims[1]
            print('Ring detected! (hopefully)')
            corners, ids, rejected_corners = cv2.aruco.detectMarkers(cv_image, dictm, parameters=params)

            # Increase proportionally if you want a larger image
            image_size = (351, 248, 3)
            marker_side = 50

            img_out = np.zeros(image_size, np.uint8)
            out_pts = np.array([[marker_side / 2, img_out.shape[0] - marker_side / 2],
                                [img_out.shape[1] - marker_side / 2, img_out.shape[0] - marker_side / 2],
                                [marker_side / 2, marker_side / 2],
                                [img_out.shape[1] - marker_side / 2, marker_side / 2]])

            src_points = np.zeros((4, 2))
            cens_mars = np.zeros((4, 2))

            if not ids is None:
                if len(ids) == 4:
                    print('4 Markers detected')

                    for idx in ids:
                        # Calculate the center point of all markers
                        cors = np.squeeze(corners[idx[0] - 1])
                        cen_mar = np.mean(cors, axis=0)
                        cens_mars[idx[0] - 1] = cen_mar
                        cen_point = np.mean(cens_mars, axis=0)

                    for coords in cens_mars:
                        #  Map the correct source points
                        if coords[0] < cen_point[0] and coords[1] < cen_point[1]:
                            src_points[2] = coords
                        elif coords[0] < cen_point[0] and coords[1] > cen_point[1]:
                            src_points[0] = coords
                        elif coords[0] > cen_point[0] and coords[1] < cen_point[1]:
                            src_points[3] = coords
                        else:
                            src_points[1] = coords

                    x_mean = src_points.mean(axis=0)[0]
                    # print(x_mean)

                    # cv2.imshow('OCR image', cv_image)
                    # cv2.waitKey(30)

                    h, status = cv2.findHomography(src_points, out_pts)
                    img_out = cv2.warpPerspective(cv_image, h, (img_out.shape[1], img_out.shape[0]))

                    ################################################
                    #### Extraction of digits starts here
                    ################################################

                    # Cut out everything but the numbers
                    # print(np.shape(img_out))
                    img_out = img_out[125:221, 52:202, :]

                    # Convert the image to grayscale
                    img_out = cv2.cvtColor(img_out, cv2.COLOR_BGR2GRAY)

                    # Option 1 - use ordinairy threshold the image to get a black and white image
                    # ret,img_out = cv2.threshold(img_out,100,255,0)

                    # Option 1 - use adaptive thresholding
                    # img_out = cv2.adaptiveThreshold(img_out, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11,
                    #                                 5)
                    # Use Otsu's thresholding
                    ret, img_out = cv2.threshold(img_out, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                    img_left = img_out[:, :69]
                    img_right = img_out[:, 81:]

                    dataset = []

                    img_np_left = np.array(img_left)
                    img_np_left = img_np_left.flatten()
                    dataset.append(img_np_left)

                    img_np_right = np.array(img_right)
                    img_np_right = img_np_right.flatten()
                    dataset.append(img_np_right)

                    X = np.array(dataset)

                    y = model.predict(X)
                    y = [int(i) for i in y]

                    # tesseract is just to know when we look at the numbers
                    config = '--psm 13 outputbase nobatch digits'

                    # Visualize the image we are passing to Tesseract
                    cv2.imshow('OCR warped', img_out)
                    cv2.waitKey(1)

                    # Extract text from image
                    text = pytesseract.image_to_string(img_out, config=config)

                    # Check and extract data from text
                    print('Extracted (pytesseract)>>', text)

                    # Remove any whitespaces from the left and right, spaces in between etc.
                    text = text.strip().replace(" ", "").replace("\n", "")

                    # If the extracted text is of the right length
                    if len(text) == 2:

                        print('The extracted datapoints (PCA svm) are x=%d, y=%d' % (y[0], y[1]))
                        if int(text[0]) != y[0] or int(text[1]) != y[1]:
                            print('\033[93m' + 'WRONG DIGITS!! pytesseract and PCA SVM do not agree' + '\033[0m')
                        msg = digits()
                        msg.x = y[0]
                        msg.y = y[1]
                        msg.timestamp = self.timestamp
                        msg.x_mean = x_mean
                        msg.img_width = img_width
                        self.pub.publish(msg)
                    else:
                        print('No numbers')

                else:
                    print('The number of markers is not ok:', len(ids))
            else:
                print('No markers found')

        elif len(candidates) == 0:
            print('No contours detected')
        else:
            print('Some contours detected, not sure if it is a ring', len(candidates))
            for elps in candidates:
                e1 = elps[0]
                e2 = elps[0]
                cv2.ellipse(cv_image, e1, (0, 255, 0), 3)
                cv2.ellipse(cv_image, e2, (0, 255, 0), 3)
        print("--------------------------")
        # cv2.imshow('Image',cv_image)
        # cv2.waitKey(1)


def main(args):
    model_name = 'PCA_learner_big.model'
    path = '/home/team_eta/ROS/OCR/models'
    service_topic = '/task2/digits'
    msg_type_string = 'digits'
    global dest_path
    dest_path = "/home/team_eta/ROS/OCR/digits_real"

    global model
    model = load(os.path.join(path, model_name))

    ring_rectifier = The_Rectifier()

    print("--------------------------")
    print("OCR ready")
    print("Publisher topic: '{}', Message type: '{}'".format(service_topic, msg_type_string))
    print("--------------------------")

    # for testing
    """
    ring_rectifier.mock_image_callback(path="/home/team_eta/ROS/OCR/rings_digits/ring_dig_31.png")
    ring_rectifier.mock_image_callback(path="/home/team_eta/ROS/OCR/rings_digits/ring_dig_73.png")
    ring_rectifier.mock_image_callback(path="/home/team_eta/ROS/OCR/rings_digits/ring_dig_23.png")
    ring_rectifier.mock_image_callback(path="/home/team_eta/ROS/OCR/rings_digits/ring_dig_58.png")
    ring_rectifier.mock_image_callback(path="/home/team_eta/ROS/OCR/rings_digits/ring_dig_10.png")
    ring_rectifier.mock_image_callback(path="/home/team_eta/ROS/OCR/rings_digits/ring_dig_98.png")
    """

    try:
        rospy.spin()
    except KeyboardInterrupt:
        print("Shutting down")

    cv2.destroyAllWindows()


if __name__ == '__main__':
    main(sys.argv)
