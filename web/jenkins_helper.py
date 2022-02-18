import os,requests,re
from bs4 import BeautifulSoup
from logzero import logger

from jenkinsapi import jenkins

jenkins_url   = os.environ.get('AT_JENKINS_URL','http://172.16.246.89:8080/')
jenkins_name = os.environ.get('AT_JENKINS_NAME','wh.huang@tuya.com')
jenkins_token = os.environ.get('AT_JENKINS_TOKEN','11992db19960280f1213ccb39ad9d0ee15')


class TJenkins(object):
    def __init__(self):
        self.japi : Jenkins = Jenkins(jenkins_url,username=jenkins_name,password=jenkins_token,lazy=True)
        pass
    
    @staticmethod
    def lock_resource():
        auth = requests.auth.HTTPBasicAuth(jenkins_name.encode('utf-8'), jenkins_token.encode('utf-8'))
        
        res = requests.get(jenkins_url + 'lockable-resources',auth = auth)
        res.raise_for_status()
        
        html_soup = BeautifulSoup(res.text, "html.parser")
        main = html_soup.find("div", id="main-panel")
        table = main.find("table", class_="pane")
        rows = table.find_all("tr", attrs={"data-resource-name":  re.compile(".*")})
        # Iterate through rows to extract resource name state and ownership
        resources = list(map(data_resource_from_row, rows))
        logger.debug(resources)
        return resources
        
def data_resource_from_row(row):
    name = str(row.attrs["data-resource-name"])
    columns = row.find_all("td")
    state_cell = columns[1]
    state_cell_text = state_cell.text.strip()
    parts = state_cell_text.split("\n")
    state, *parts = parts
    owner = parts[1].strip() if len(parts) > 1 else None
    label = str(columns[2].text)
    return dict(name=name, state=state, owner=owner, label=label)


def main():
    TJenkins.lock_resource()

if __name__ == '__main__':
    main()
    