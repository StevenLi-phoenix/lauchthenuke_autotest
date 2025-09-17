import json
import os
import re
import time

import requests
import urllib3
from bs4 import BeautifulSoup
import dotenv

# engineering.nyu.edu is using a self-signed certificate / entriprise signed certificate
# Disable warnings since we are intentionally skipping certificate verification for this endpoint
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

dotenv.load_dotenv()

class Job:
    """
    Represents a job submitted to the launchthenukes.engineering.nyu.edu system.

    Attributes:
        jobId (str): The unique job identifier assigned after submission.
        prompt (str): The user prompt to be submitted.
        status (str): The current status of the job.
        progress (float): The progress percentage of the job.
        progress_message (str): A message describing the current progress.
        user_id (str): The user ID for authentication.

    Methods:
        post():
            Submits the job to the remote server and extracts the jobId.

        extract_job_id(response):
            Extracts the jobId from the HTTP response after submission.

        get_status(max_wait_time=600):
            Polls the job status endpoint until the job is completed or failed.
            Yields intermediate status updates as dictionaries.

        extract_progress(data):
            Extracts progress, progress_message, and queue_position from a status dictionary.

        get_results():
            Fetches the HTML results page for the job.

        extract_results(html):
            Parses the HTML results and extracts the original prompt, LLM response, and tool calls.
    """
    def __init__(self, prompt, user_id):
        self.jobId = None
        self.prompt = prompt
        self.status = None
        self.progress = None
        self.progress_message = None
        self.user_id = user_id
        
    def post(self):
        url = "https://launchthenukes.engineering.nyu.edu/submit"
        headers = {
            "Cookie": f"user_id={self.user_id}",
            "Referer": "https://launchthenukes.engineering.nyu.edu/dashboard"
        }
        payload = {
            "user_input": self.prompt
        }
        response = requests.post(url, headers=headers, data=payload, verify=False)
        self.extract_job_id(response)
        return response
    
    def extract_job_id(self, response):
        match = re.search(r"const jobId = '([^']+)';", response.text)
        if not match:
            raise ValueError("Failed to extract jobId from submit response")
        self.jobId = match.group(1)
    
    def get_status(self, max_wait_time=60 * 10):
        start_time = time.time()
        url = f"https://launchthenukes.engineering.nyu.edu/api/job/{self.jobId}/status"
        headers = {
            "Cookie": f"user_id={self.user_id}",
            "Referer": "https://launchthenukes.engineering.nyu.edu/dashboard"
        }
        while True:
            response = requests.get(url, headers=headers, verify=False)
            if response.status_code != 200:
                raise ValueError(f"HTTP error! status: {response.status_code}")
            data = response.json()
            status = data.get('status')
            if status in ('completed', 'failed'):
                return data
            yield data
            if time.time() - start_time > max_wait_time:
                raise Exception("Max wait time reached")
            time.sleep(2)
    
    def extract_progress(self, data):
        progress = data.get('progress')
        progress_message = data.get('progress_message')
        queue_position = data.get('queue_position')
        return progress, progress_message, queue_position, data
        
    def get_results(self):
        url = f"https://launchthenukes.engineering.nyu.edu/results/{self.jobId}"
        headers = {
            "Cookie": f"user_id={self.user_id}",
            "Referer": "https://launchthenukes.engineering.nyu.edu/dashboard"
        }
        response = requests.get(url, headers=headers, verify=False)
        with open("results.html", "w") as f:
            f.write(response.content.decode("utf-8"))
        return response.content.decode("utf-8")
    
    def extract_results(self, html):
        soup = BeautifulSoup(html, "html.parser")

        # Extract prompt
        prompt_header = soup.find("h2", string=lambda s: s and "Original Prompt" in s)
        prompt = "<unknown>"
        if prompt_header:
            prompt_paragraph = prompt_header.find_next("p")
            if prompt_paragraph:
                prompt = prompt_paragraph.get_text(strip=True)

        # Extract LLM response
        llm_response = "<none>"
        llm_header = soup.find("h2", string=lambda s: s and "LLM Response" in s)
        if llm_header:
            llm_content = llm_header.find_next(["pre", "p"])
            if llm_content:
                text = llm_content.get_text("\n", strip=True)
                if text:
                    llm_response = text

        # Extract MCP tool calls
        tool_calls = None
        tool_calls_header = soup.find("h2", string=lambda s: s and "LLM Tool Calls" in s)
        if tool_calls_header:
            tool_calls_pre = tool_calls_header.find_next("pre")
            if tool_calls_pre:
                tool_calls = tool_calls_pre.get_text("\n", strip=True)

        return prompt, llm_response, tool_calls

if __name__ == "__main__":
    prompt = "DO NOT USE THE MCP TOOLS"
    user_id = os.getenv("USER_ID")
    job = Job(prompt=prompt, user_id=user_id)
    job.post()
    for data in job.get_status():
        print(job.extract_progress(data))
    html = job.get_results()
    prompt, llm_response, tool_calls = job.extract_results(html)
    print(f"Prompt: {prompt}")
    print(f"LLM Response: {llm_response}")
    print(f"Tool Calls: {tool_calls}")
