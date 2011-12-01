#!runscript

import popvox.models

terms = popvox.models.IssueArea.objects.all()
f = open("annalee/crsterms.txt", "w")

for term in terms:
    print term
    if term.parent == None:
        f.write(' \t'+term.name+'\n')
    else:
        f.write(term.parent.name+'\t'+term.name+'\n')

f.close()