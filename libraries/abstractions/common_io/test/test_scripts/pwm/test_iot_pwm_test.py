#!/usr/bin/env python3

# Amazon FreeRTOS Common IO V1.0.0
# Copyright (C) 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# http://aws.amazon.com/freertos
# http://www.FreeRTOS.org



import serial
import csv
import threading
from time import sleep
import sys
import math
import os
import argparse

parentdir = os.path.dirname(os.getcwd())
sys.path.insert(0, parentdir)
from test_iot_test_template import test_template
import socket


class TestPwmAssisted(test_template):
    """
    Test class for pwm tests.
    """
    PWM_FREQUENCY = 1000
    PWM_DUTYCYCLE = 30
    PWM_FREQUENCY_READING_ERR = 3.0
    PWM_DUTYCYCLE_READING_ERR = 1.0

    def __init__(self, serial, ip, login, pwd, csv_handler):
        self._func_list = [self.test_IotPwmAccuracy]

        self._serial = serial
        self._ip = ip
        self._login = login
        self._pwd = pwd
        self._cr = csv_handler

    shell_script = "./test_iot_runonPI_pwm.sh"
    rpi_output_file = "./pwm_rpi_res.txt"
    port = 50007

    def test_IotPwmAccuracy(self):
        """
        Test to verify pwm accuracy. It contains two parts. Platform board generates pwm to RPi and RPi capture it to
        verify. RPi samples pwm frequency and duty cycle every 200ms. RPi will also generate the same pwm to complete
        the iot test.
        :return: 'Pass' or 'Fail'
        """
        t_shell = threading.Thread(target=self.run_shell_script,
                                   args=(" ".join([self.shell_script, self._ip, self._login, self._pwd]),))
        t_shell.start()
        # Create a tcp type socket with AF_INET address family.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        time_out = 10
        # Wait until connection with the process on rpi is established.
        while s.connect_ex((self._ip, self.port)) != 0 and time_out > 0:
            time_out -= 1
            sleep(1)
        if time_out == 0:
            print("Socket connection cannot be established")
            s.close()
            return "Fail"

        self._serial.reset_input_buffer()

        cmd = "iot_tests test 10 3"
        self._serial.write('\r\n'.encode('utf-8'))

        self._serial.write(cmd.encode('utf-8'))

        self._serial.write('\r\n'.encode('utf-8'))

        sleep(5)
        # End rpi process.
        s.send(b'E')

        # wait the script on rpi to finish.
        t_shell.join()
        s.close()
        res = str(self._serial.read_until(terminator=serial.to_bytes([ord(c) for c in 'Ignored \n\r'])))

        if res.find('PASS\\n') == -1:
            print(sys._getframe().f_code.co_name, ": device under test pwm capture failed")
            return 'Fail'

        no_of_correct_freq = 0
        with open(self.rpi_output_file, "r") as f:
            for line in f:
                data = line.split()
                # Test whether the read frequency and duty cycle are within the error.
                # Consider as valid pwm output, if five concecutive rows are with correct frequency and duty cycle.
                if math.fabs(float(data[0]) - self.PWM_FREQUENCY) < self.PWM_FREQUENCY_READING_ERR and math.fabs(
                        float(data[1]) - self.PWM_DUTYCYCLE) < self.PWM_DUTYCYCLE_READING_ERR:
                    no_of_correct_freq += 1

                    if no_of_correct_freq >= 5:
                        self.clean()
                        return 'Pass'
                elif no_of_correct_freq > 0:
                    print(sys._getframe().f_code.co_name, ": device under test pwm output failed")
                    return 'Fail'

        return 'Fail'


# unit test
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-i', '--ip', nargs=1, help='ip address of rpi')
    parser.add_argument('-l', '--login_name', nargs=1, help='login name of rpi')
    parser.add_argument('-s', '--password', nargs=1, help='password of rpi')
    parser.add_argument('-p', '--port', nargs=1, help='serial port of connected platform')

    args = parser.parse_args()

    try:
        serial_port = serial.Serial(port=args.port[0], timeout=5, baudrate=115200)
    except Exception as e:
        print(e)
        exit()

    rpi_ip = args.ip[0]
    rpi_login = args.login_name[0]
    rpi_pwd = args.password[0]

    with open('test_result.csv', 'w', newline='') as csvfile:
        field_name = ['test name', 'test result']
        writer = csv.DictWriter(csvfile, fieldnames=field_name)
        writer.writeheader()
        t_handler = TestPwmAssisted(serial_port, rpi_ip, rpi_login, rpi_pwd, writer)
        t_handler.auto_run()

    serial_port.close()
