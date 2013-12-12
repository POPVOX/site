#!runscript

import popvox.models as pv

sep = "\t"

states = {'AL': 7, 'AK': 1, 'AZ': 9, 'AR': 4, 'CA': 53, 'CO': 7, 'CT': 5, 'DE': 1, 'FL': 27, 'GA': 14, 'HI': 2, 'ID': 2, 'IL': 18, 'IN': 9, 'IA': 4, 'KS': 4, 'KY': 6, 'LA': 6, 'ME': 2, 'MD': 8, 'MA': 9, 'MI': 14, 'MN': 8, 'MS': 4, 'MO': 8, 'MT': 1, 'NE': 3, 'NV': 4, 'NH': 2, 'NJ': 12, 'NM': 3, 'NY': 27, 'NC': 13, 'ND': 1, 'OH': 16, 'OK': 5, 'OR': 5, 'PA': 18, 'RI': 2, 'SC': 7, 'SD': 1, 'TN': 9, 'TX': 36, 'UT': 4, 'VT': 1, 'VA': 11, 'WA': 10, 'WV': 3, 'WI': 8, 'WY': 1, 'DC': 1, 'GU': 1, 'AS': 1, 'MP': 1, 'PR': 1, 'VI': 1}

currentaddresses = []
userprofs = pv.UserProfile.objects.all()
for user in userprofs:
    try:
        address = user.most_recent_address()
    except:
        continue
    currentaddresses.append(address)

with open('comments-users-statedist.csv','w') as cusd:
    cusd.write ('state:' +sep+ 'district:' +sep+ 'users:' +sep+ 'comments:' )
    for state, distcount in states:
        comments = pv.UserComment.objects.filter(address__state=state).count()
        users = len([x for x in currentaddresses if x.state == state])
        cusd.write( str(state) +sep+ 'all' +sep+ str(comments) +sep+ str(users) )
        
        if distcount > 1:
            districts = range(1,int(distcount)+1)
            for district in districts:
                comments = pv.UserComment.objects.filter(address__state=state, congressionaldistrict=district).count()
                users = len([x for x in users if x.congressionaldistrict == district])
                cusd.write( str(state) +sep+ str(district) +sep+ str(comments) +sep+ str(users) )