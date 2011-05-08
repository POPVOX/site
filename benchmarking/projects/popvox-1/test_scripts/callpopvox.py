import mechanize

class Transaction:
    def run(self):
        br = mechanize.Browser()
        br.set_handle_robots(False)
        resp = br.open('https://ec2-50-17-164-57.compute-1.amazonaws.com')
        resp.read()
