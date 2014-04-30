from django.core.cache import cache
from django.core.cache.backends.filebased import CacheClass as FileBasedCache

import os, os.path
from datetime import datetime, date
import sys
import re
import settings

#have to do this to avoid recursive import, which causes the code to crash.
import popvox.models

#Functions to pull member objects from our database, as opposed to the govtrack functions, which pull member data from yaml and return them as dictionaries.

#TODO: "chain" roles with 'next_role' and 'prev_role' fields, and add a 'current_role' foreignkey to the moc model so that we can reduce the overhead on associating members to their seat.

def getMembersFromRoles(roles):
    mems = []
    for role in roles:
        if role.member.most_recent_role() == role:
            mems.append(role.member)
    return mems

def getMembersForState(state, moctype="all"):
    # state is the two letter abbreviation.
    #moctype choices are "all", "sen", and "rep".
    if moctype == "all":
        roles = popvox.models.MemberOfCongressRole.objects.filter(state=state, member__current=True)
    else:
        roles = popvox.models.MemberOfCongressRole.objects.filter(state=state, memtype=moctype, member__current=True)
    return getMembersFromRoles(roles)

def getMembersOfCongressForDistrict(state, district, moctype="all"):
    # state is the two letter abbreviation. District is an integer. 
    if moctype == "sen":
        roles = popvox.models.MemberOfCongressRole.objects.filter(state=state, memtype="sen", member__current=True)
    elif moctype == "rep":
        roles = popvox.models.MemberOfCongressRole.objects.filter(state=state, memtype="rep", district=district, member__current=True)
    else: #get both.
        roles = list(popvox.models.MemberOfCongressRole.objects.filter(state=state, memtype="sen", member__current=True))
        roles = roles + list(popvox.models.MemberOfCongressRole.objects.filter(state=state, memtype="rep", district=district, member__current=True)) 
    return getMembersFromRoles(roles)