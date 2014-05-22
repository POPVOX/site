#!runscript

from articles.models import Article, MARKUP_HTML
from django.contrib.auth.models import User
import re
from BeautifulSoup import BeautifulSoup, Tag

annalee = User.objects.get(id=13034)
josh    = User.objects.get(id=44315) #wp id 3
marci   = User.objects.get(id=161) #wp id 2
rachna  = User.objects.get(id=58) #wp id 4


# clear existing table !!
Article.objects.all().delete()

dump = open("../../blog_dump.tsv")


for post in dump:
    post = post.split("\t")
    if post[0]=="post_author":
        continue
    
    if len(post[2]) > 100:
        print post[1]+": "+post[2]

    art = Article()
    art.auto_tag = False
    art.title = post[2][0:100]
    art.slug =  post[3][:50] if len(post[3]) > 50 else post[3]
    art.status_id = '2'
    #converting wordpress author ids to django ids:
    if post[0] == '2':
        art.author = marci
    elif post[0] == '3':
        art.author = josh
    else: 
        art.author = rachna
    art.description = post[4]
    art.markup = MARKUP_HTML
    #cleaning up article markup (TODO: fix this):
    
    # insert paragraphs based on hard line breaks
    content = post[5].replace(r"\n", "\n").replace(r"\t", "\t")
    def ptag(line):
        if not line.strip().startswith("<"):
            line = "<p>" + line + "</p>"
        return line
    content = "\n".join([ptag(line) for line in re.split("[\r\n][\r\n]+", content)])

    # clean up invalid HTML: li not inside a ul
    soup = BeautifulSoup(content)
    for tag in soup.findAll("li"):
       if tag.parent.name not in ("ol", "ul"):
          parent = Tag(soup, "ul")
          tag.replaceWith(parent)
          parent.insert(0, tag)
    content = soup.prettify()
    
    art.content = content
    art.publish_date = post[1]
    
    art.save()


