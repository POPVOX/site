#! /usr/bin/python
import mechanize
import time


class Transaction:
    def run(self):
        self.custom_timers = {}

        br = mechanize.Browser()
        br.set_handle_robots(False)
        
        start_timer = time.time()
        resp = br.open('https://ec2-50-17-164-57.compute-1.amazonaws.com/')
        resp.read()
        latency = time.time() - start_timer
        
        self.custom_timers['path1'] = latency
