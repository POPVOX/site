	var default_state;
	var default_district;
	var dist_report_state = "";
	var dist_report_district = "";
	var mem_report_state = "";
	var mem_report_member = "";
	var start = 0;
	var count = 50;
	var isloading = false;

var memurls = {
'WA': [['Sen. Maria Cantwell [D, WA]', 'sen-maria-cantwell-wa'],
['Sen. Patty Murray [D, WA]', 'sen-patty-murray-wa'],
['Rep. Suzan DelBene [D, WA-1]', 'rep-suzan-delbene-wa'],
['Rep. Rick Larsen [D, WA-2]', 'rep-rick-larsen-wa'],
['Rep. Jaime Herrera Beutler [R, WA-3]', 'rep-jaime-herrera-wa'],
['Rep. Doc Hastings [R, WA-4]', 'rep-doc-hastings-wa'],
['Rep. Cathy McMorris Rodgers [R, WA-5]', 'rep-cathy-mcmorris-rodgers-wa'],
['Rep. Derek Kilmer [D, WA-6]', 'rep-derek-kilmer-wa'],
['Rep. James McDermott [D, WA-7]', 'rep-jim-mcdermott-wa'],
['Rep. Dave Reichert [R, WA-8]', 'rep-dave-reichert-wa'],
['Rep. Adam Smith [D, WA-9]', 'rep-adam-smith-wa'],
['Rep. Dennis Heck [D, WA-10]', 'rep-dennis-heck-wa']],

'DE': [['Sen. Thomas Carper [D, DE]', 'sen-tom-carper-de'],
['Sen. Chris Coons [D, DE]', 'sen-chris-coons-de'],
['Rep. John Carney [D, DE-0]', 'rep-john-carney-de']],

'DC': [['Del. Eleanor Norton [D, DC-0]', 'del-eleanor-norton-dc']],

'WI': [['Sen. Tammy Baldwin [D, WI]', 'sen-tammy-baldwin-wi'],
['Sen. Ron Johnson [R, WI]', 'sen-ron-johnson-wi'],
['Rep. Paul Ryan [R, WI-1]', 'rep-paul-ryan-wi'],
['Rep. Mark Pocan [D, WI-2]', 'rep-mark-pocan-wi'],
['Rep. Ronald Kind [D, WI-3]', 'rep-ron-kind-wi'],
['Rep. Gwen Moore [D, WI-4]', 'rep-gwen-moore-wi'],
['Rep. James Sensenbrenner [R, WI-5]', 'rep-jim-sensenbrenner-wi'],
['Rep. Thomas Petri [R, WI-6]', 'rep-tom-petri-wi'],
['Rep. Sean Duffy [R, WI-7]', 'rep-sean-duffy-wi'],
['Rep. Reid Ribble [R, WI-8]', 'rep-reid-ribble-wi']],

'WV': [['Sen. John Rockefeller [D, WV]', 'sen-jay-rockefeller-wv'],
['Sen. Joe Manchin [D, WV]', 'sen-joe-manchin-wv'],
['Rep. Shelley Capito [R, WV-2]', 'rep-shelley-capito-wv'],
['Rep. Nick Rahall [D, WV-3]', 'rep-nick-rahall-wv'],
['Rep. David McKinley [R, WV-1]', 'rep-david-mckinley-wv']],

'HI': [['Sen. Brian Schatz [D, HI]', 'sen-brian-schatz-hi'],
['Sen. Mazie Hirono [D, HI]', 'sen-mazie-hirono-hi'],
['Rep. Colleen Hanabusa [D, HI-1]', 'rep-colleen-hanabusa-hi'],
['Rep. Tulsi Gabbard [D, HI-2]', 'rep-tulsi-gabbard-hi']],

'FL': [['Sen. Bill Nelson [D, FL]', 'sen-bill-nelson-fl'],
['Sen. Marco Rubio [R, FL]', 'sen-marco-rubio-fl'],
['Rep. Jeff Miller [R, FL-1]', 'rep-jeff-miller-fl'],
['Rep. Steve Southerland [R, FL-2]', 'rep-steve-southerland-fl'],
['Rep. Ted Yoho [R, FL-3]', 'rep-ted-yoho-fl'], 
['Rep. Ander Crenshaw [R, FL-4]', 'rep-ander-crenshaw-fl'],
['Rep. Corrine Brown [D, FL-5]', 'rep-corrine-brown-fl'],
['Rep. Ron DeSantis [R, FL-6]', 'rep-ron-desantis-fl'],
['Rep. John Mica [R, FL-7]', 'rep-john-mica-fl'],
['Rep. Bill Posey [R, FL-8]', 'rep-bill-posey-fl'],
['Rep. Alan Grayson [D, FL-9]', 'rep-alan-Grayson-fl'],
['Rep. Daniel Webster [R, FL-10]', 'rep-daniel-webster-fl'],
['Rep. Rich Nugent [R, FL-11]', 'rep-rich-nugent-fl'],
['Rep. Gus Bilirakis [R, FL-12]', 'rep-gus-bilirakis-fl'],
['Rep. Bill Young [R, FL-13]', 'rep-bill-young-fl'],
['Rep. Kathy Castor [D, FL-14]', 'rep-kathy-castor-fl'],
['Rep. Dennis Ross [R, FL-15]', 'rep-dennis-ross-fl'],
['Rep. Vern Buchanan [R, FL-16]', 'rep-vern-buchanan-fl'],
['Rep. Tom Rooney [R, FL-17]', 'rep-tom-rooney-fl'],
['Rep. Patrick Murphy [D, FL-18]', 'rep-patrick-murphy-fl'],
['Rep. Trey Radel [R, FL-19]', 'rep-trey-radel-fl'],
['Rep. Alcee Hastings [D, FL-20]', 'rep-alcee-hastings-fl'], 
['Rep. Ted Deutch [D, FL-21]', 'rep-ted-deutch-fl'],
['Rep. Lois Frankel [D, FL-22]', 'rep-lois-frankel-fl'],
['Rep. Debbie Wasserman-Shultz [D, FL-23]', 'rep-debbie-wasserman-schultz-fl'],
['Rep. Frederica Wilson [D, FL-24]', 'rep-frederica-wilson-fl'],
['Rep. Mario Diaz-Balart [R, FL-25]', 'rep-mario-diaz-balart-fl'],
['Rep. Joe Garcia [D, FL-26]', 'rep-joe-garcia-fl']
['Rep. Ileana Ros-Lehtinen [R, FL-27]', 'rep-ileana-ros-lehtinen-fl']],

'WY': [['Sen. Michael Enzi [R, WY]', 'sen-mike-enzi-wy'],
['Sen. John Barrasso [R, WY]', 'sen-john-barrasso-wy'],
['Rep. Cynthia Lummis [R, WY-0]', 'rep-cynthia-lummis-wy']],

'NH': [['Sen. Kelly Ayotte [R, NH]', 'sen-kelly-ayotte-nh'],
['Sen. Jeanne Shaheen [D, NH]', 'sen-jeanne-shaheen-nh'],
['Rep. Carol Shea-Porter [D, NH-1]', 'rep-carol-shea-porter-nh'],
['Rep. Ann Kuster [D, NH-2]', 'rep-ann-kuster-nh']],

'NJ': [['Sen. Frank Lautenberg [D, NJ]', 'sen-frank-lautenberg-nj'],
['Sen. Robert Menéndez [D, NJ]', 'sen-robert-menendez-nj'],
['Rep. Robert Andrews [D, NJ-1]', 'rep-robert-andrews-nj'],
['Rep. Frank LoBiondo [R, NJ-2]', 'rep-frank-lobiondo-nj'],
['Rep. Jon Runyan [R, NJ-3]', 'rep-jon-runyan-nj'],
['Rep. Christopher Smith [R, NJ-4]', 'rep-chris-smith-nj'],
['Rep. Scott Garrett [R, NJ-5]', 'rep-scott-garrett-nj'],
['Rep. Frank Pallone [D, NJ-6]', 'rep-frank-pallone-nj'],
['Rep. Leonard Lance [R, NJ-7]', 'rep-leonard-lance-nj'],
['Rep. William Pascrell [D, NJ-9]', 'rep-bill-pascrell-nj'],
['Rep. Albio Sires [D, NJ-8]', 'rep-albio-sires-nj'],
['Rep. Donald Payne [D, NJ-10]', 'rep-donald-payne-jr-nj'],
['Rep. Rodney Frelinghuysen [R, NJ-11]', 'rep-rodney-frelinghuysen-nj'],
['Rep. Rush Holt [D, NJ-12]', 'rep-rush-holt-nj']],

'NM': [['Sen. Martin Heinrich [D, NM]', 'sen-martin-heinrich-nm'],
['Sen. Tom Udall [D, NM]', 'sen-tom-udall-nm'],
['Rep. Michelle Grisham [D, NM-1]', 'rep-michelle-grisham-nm'],
['Rep. Steven Pearce [R, NM-2]', 'rep-steve-pearce-nm'],
['Rep. Ben Luján [D, NM-3]', 'rep-ben-lujan-nm']],

'TX': [['Sen. John Cornyn [R, TX]', 'sen-john-cornyn-tx'],
['Sen. Ted Cruz [R, TX]', 'sen-ted-cruz-tx'],
['Rep. Louis Gohmert [R, TX-1]', 'rep-louie-gohmert-tx'],
['Rep. Ted Poe [R, TX-2]', 'rep-ted-poe-tx'],
['Rep. Samuel Johnson [R, TX-3]', 'rep-sam-johnson-tx'],
['Rep. Ralph Hall [R, TX-4]', 'rep-ralph-hall-tx'],
['Rep. Jeb Hensarling [R, TX-5]', 'rep-jeb-hensarling-tx'],
['Rep. Joe Barton [R, TX-6]', 'rep-joe-barton-tx'],
['Rep. John Culberson [R, TX-7]', 'rep-john-culberson-tx'],
['Rep. Kevin Brady [R, TX-8]', 'rep-kevin-brady-tx'],
['Rep. Al Green [D, TX-9]', 'rep-al-green-tx'],
['Rep. Michael McCaul [R, TX-10]', 'rep-michael-mccaul-tx'],
['Rep. Michael Conaway [R, TX-11]', 'rep-mike-conaway-tx'],
['Rep. Kay Granger [R, TX-12]', 'rep-kay-granger-tx'],
['Rep. William Thornberry [R, TX-13]', 'rep-mac-thornberry-tx'],
['Rep. Randy Webber [R, TX-14]', 'rep-randy-weber-tx'],
['Rep. Rubén Hinojosa [D, TX-15]', 'rep-ruben-hinojosa-tx'],
["Rep. Beto O'Rourke [D, TX-16]", 'rep-beto-orourke-tx'],
['Rep. Bill Flores [R, TX-17]', 'rep-bill-flores-tx'],
['Rep. Sheila Jackson-Lee [D, TX-18]', 'rep-sheila-jackson-lee-tx'],
['Rep. Randy Neugebauer [R, TX-19]', 'rep-randy-neugebauer-tx'],
['Rep. Joaquin Castro [D, TX-20]', 'rep-joaquin-castro-tx'],
['Rep. Lamar Smith [R, TX-21]', 'rep-lamar-smith-tx'],
['Rep. Pete Olson [R, TX-22]', 'rep-pete-olson-tx'],
['Rep. Pete Gallego [D, TX-23]', 'rep-pete-gallego-tx'],
['Rep. Kenny Marchant [R, TX-24]', 'rep-kenny-marchant-tx'],
['Rep. Roger Williams [R, TX-25]', 'rep-roger-williams-tx'],
['Rep. Michael Burgess [R, TX-26]', 'rep-michael-burgess-tx'],
['Rep. Blake Farenthold [R, TX-27]', 'rep-blake-farenthold-tx'],
['Rep. Henry Cuellar [D, TX-28]', 'rep-henry-cuellar-tx'],
['Rep. Raymond Green [D, TX-29]', 'rep-gene-green-tx'],
['Rep. Eddie Johnson [D, TX-30]', 'rep-eddie-johnson-tx'],
['Rep. John Carter [R, TX-31]', 'rep-john-carter-tx'],
['Rep. Peter Sessions [R, TX-32]', 'rep-pete-sessions-tx'],
['Rep. Marc Veasey [D, TX-33]', 'rep-mark-veasey-tx'],
['Rep. Filemon Vela, Jr. [D, TX-34]', 'rep-filemon-vela-tx'],
['Rep. Lloyd Doggett [D, TX-35]', 'rep-lloyd-doggett-tx'],
['Rep. Steve Stockman [R, TX-36]', 'rep-steve-stockman-tx']],

'LA': [['Sen. Mary Landrieu [D, LA]', 'sen-mary-landrieu-la'],
['Sen. David Vitter [R, LA]', 'sen-david-vitter-la'],
['Rep. Steve Scalise [R, LA-1]', 'rep-steve-scalise-la'],
['Rep. Cedric Richmond [D, LA-2]', 'rep-cedric-richmond-la'],
['Rep. Charles Boustany [R, LA-3]', 'rep-charles-boustany-la'],
['Rep. John Fleming [R, LA-4]', 'rep-john-fleming-la'],
['Rep. Rodney Alexander [R, LA-5]', 'rep-rodney-alexander-la'],
['Rep. Bill Cassidy [R, LA-6]', 'rep-bill-cassidy-la']],

'NC': [['Sen. Richard Burr [R, NC]', 'sen-richard-burr-nc'],
['Sen. Kay Hagan [D, NC]', 'sen-kay-hagan-nc'],
['Rep. George Butterfield [D, NC-1]', 'rep-g-k-butterfield-nc'],
['Rep. Renee Ellmers [R, NC-2]', 'rep-renee-ellmers-nc'],
['Rep. Walter Jones [R, NC-3]', 'rep-walter-jones-nc'],
['Rep. David Price [D, NC-4]', 'rep-david-price-nc'],
['Rep. Virginia Foxx [R, NC-5]', 'rep-virginia-foxx-nc'],
['Rep. Howard Coble [R, NC-6]', 'rep-howard-coble-nc'],
['Rep. Mike McIntyre [D, NC-7]', 'rep-mike-mcintyre-nc'],
['Rep. Richard Hudson [R, NC-8]', 'rep-richard-hudson-nc'],
['Rep. Robert Pittenger [R, NC-9]', 'rep-robert-pittenger-nc'],
['Rep. Patrick McHenry [R, NC-10]', 'rep-patrick-mchenry-nc'],
['Rep. Mark Meadows [R, NC-11]', 'rep-mark-meadows-nc'],
['Rep. Melvin Watt [D, NC-12]', 'rep-mel-watt-nc'],
['Rep. George Holding [R, NC-13]', 'rep-george-holding-nc']],

'ND': [['Sen. Heidi Heitkamp [D, ND]', 'sen-heidi-heitkamp-nd'],
['Sen. John Hoeven [R, ND]', 'sen-john-hoeven-nd'],
['Rep. Kevin Cramer [R, ND-0]', 'rep-kevin-cramer-nd']],

'NE': [['Sen. Deb Fisher [R, NE]', 'sen-deb-fisher-ne'],
['Sen. Mike Johanns [R, NE]', 'sen-mike-johanns-ne'],
['Rep. Jeffrey Fortenberry [R, NE-1]', 'rep-jeff-fortenberry-ne'],
['Rep. Lee Terry [R, NE-2]', 'rep-lee-terry-ne'],
['Rep. Adrian Smith [R, NE-3]', 'rep-adrian-smith-ne']],

'TN': [['Sen. Lamar Alexander [R, TN]', 'sen-lamar-alexander-tn'],
['Sen. Bob Corker [R, TN]', 'sen-bob-corker-tn'],
['Rep. Phil Roe [R, TN-1]', 'rep-phil-roe-tn'],
['Rep. John Duncan [R, TN-2]', 'rep-john-duncan-tn'],
['Rep. Chuck Fleischmann [R, TN-3]', 'rep-chuck-fleischmann-tn'],
['Rep. Scott DesJarlais [R, TN-4]', 'rep-scott-desjarlais-tn'],
['Rep. Jim Cooper [D, TN-5]', 'rep-jim-cooper-tn'],
['Rep. Diane Black [R, TN-6]', 'rep-diane-black-tn'],
['Rep. Marsha Blackburn [R, TN-7]', 'rep-marsha-blackburn-tn'],
['Rep. Stephen Fincher [R, TN-8]', 'rep-stephen-fincher-tn'],
['Rep. Steve Cohen [D, TN-9]', 'rep-steve-cohen-tn']],

'NY': [['Sen. Charles Schumer [D, NY]', 'sen-charles-schumer-ny'],
['Sen. Kirsten Gillibrand [D, NY]', 'sen-kirsten-gillibrand-ny'],
['Rep. Timothy Bishop [D, NY-1]', 'rep-timothy-bishop-ny'],
['Rep. Steve Israel [D, NY-3]', 'rep-steve-israel-ny'],
['Rep. Peter King [R, NY-2]', 'rep-pete-king-ny'],
['Rep. Carolyn McCarthy [D, NY-4]', 'rep-carolyn-mccarthy-ny'],
['Rep. Gregory Meeks [D, NY-5]', 'rep-gregory-meeks-ny'],
['Rep. Grace Meng [D, NY-6]', 'rep-grace-meng-ny'],
['Rep. Nydia Velazquez [D, NY-7]', 'rep-nydia-velazquez-ny'],
['Rep. Hakeem Jeffries [D, NY-8]', 'rep-hakeem-jeffries-ny'],
['Rep. Yvette Clarke [D, NY-9]', 'rep-yvette-clarke-ny'],
['Rep. Jerrold Nadler [D, NY-10]', 'rep-jerrold-nadler-ny'],
['Rep. Michael Grimm [R, NY-11]', 'rep-michael-grim-ny'],
['Rep. Carolyn Maloney [D, NY-12]', 'rep-carolyn-maloney-ny'],
['Rep. Charles Rangel [D, NY-13]', 'rep-charles-rangel-ny'],
['Rep. Joe Crowley [D, NY-14]', 'rep-joe-crowley-ny'],
['Rep. Jose Serrano [D, NY-15]', 'rep-jose-serrano-ny'],
['Rep. Eliot Engel [D, NY-16]', 'rep-eliot-engel-ny'],
['Rep. Nita Lowey [D, NY-17]', 'rep-nita-lowey-ny'],
['Rep. Sean Maloney [D, NY-18]', 'rep-sean-maloney-ny'],
['Rep. Chris Gibson [R, NY-19]', 'rep-christopher-gibson-ny'],
['Rep. Paul Tonko [D, NY-20]', 'rep-paul-tonko-ny'],
['Rep. Daniel Maffei [D, NY-24]', 'rep-daniel-maffei-ny'],
['Rep. William Owens [D, NY-21]', 'rep-bill-owens-ny'],
['Rep. Richard Hanna [R, NY-22]', 'rep-richard-hanna-ny'],
['Rep. Chris Collins [R, NY-27]', 'rep-chris-collins-ny'],
['Rep. Brian Higgins [D, NY-26]', 'rep-brian-higgins-ny'],
['Rep. Louise Slaughter [D, NY-25]', 'rep-louise-slaughter-ny'],
['Rep. Tom Reed [R, NY-23]', 'rep-tom-reed-ny']],
'PA': [['Sen. Robert Casey [D, PA]', 'sen-robert-casey-pa'],
['Sen. Patrick Toomey [R, PA]', 'sen-pat-toomey-pa'],
['Rep. Robert Brady [D, PA-1]', 'rep-robert-brady-pa'],
['Rep. Chaka Fattah [D, PA-2]', 'rep-chaka-fattah-pa'],
['Rep. Mike Kelly [R, PA-3]', 'rep-mike-kelly-pa'],
['Rep. Scott Perry [R, PA-4]', 'rep-scott-perry-pa'],
['Rep. Glenn Thompson [R, PA-5]', 'rep-glenn-thompson-pa'],
['Rep. Jim Gerlach [R, PA-6]', 'rep-jim-gerlach-pa'],
['Rep. Patrick Meehan [R, PA-7]', 'rep-patrick-meehan-pa'],
['Rep. Michael Fitzpatrick [R, PA-8]', 'rep-mike-fitzpatrick-pa'],
['Rep. William Shuster [R, PA-9]', 'rep-bill-shuster-pa'],
['Rep. Thomas Marino [R, PA-10]', 'rep-thomas-marino-pa'],
['Rep. Lou Barletta [R, PA-11]', 'rep-lou-barletta-pa'],
['Rep. Keith Rothfus [R, PA-12]', 'rep-keith-rothfus-pa'],
['Rep. Allyson Schwartz [D, PA-13]', 'rep-allyson-schwartz-pa'],
['Rep. Michael Doyle [D, PA-14]', 'rep-mike-doyle-pa'],
['Rep. Charles Dent [R, PA-15]', 'rep-charles-dent-pa'],
['Rep. Joseph Pitts [R, PA-16]', 'rep-joe-pitts-pa'],
['Rep. Matt Cartwright [D, PA-17]', 'rep-matt-cartwright-pa'],
['Rep. Tim Murphy [R, PA-18]', 'rep-tim-murphy-pa']],

'AK': [['Sen. Lisa Murkowski [R, AK]', 'sen-lisa-murkowski-ak'],
['Sen. Mark Begich [D, AK]', 'sen-mark-begich-ak'],
['Rep. Donald Young [R, AK-0]', 'rep-don-young-ak']],

'NV': [['Sen. Harry Reid [D, NV]', 'sen-harry-reid-nv'],
['Sen. Dean Heller [R, NV]', 'sen-dean-heller-nv'],
['Rep. Dina Titus [D, NV-1]', 'rep-dina-titus-nv'],
['Rep. Mark Amodei [R, NV-2]', 'rep-mark-amodei-nv'],
['Rep. Joe Heck [R, NV-3]', 'rep-joe-heck-nv'],
['Rep. Steven Horsford [D, NV-4]', 'rep-steven-horsford-nv']],

'VA': [['Sen. Tim Kaine [D, VA]', 'sen-tim-kaine-va'],
['Sen. Mark Warner [D, VA]', 'sen-mark-warner-va'],
['Rep. Rob Wittman [R, VA-1]', 'rep-rob-wittman-va'],
['Rep. Scott Rigell [R, VA-2]', 'rep-scott-rigell-va'],
['Rep. Robert Scott [D, VA-3]', 'rep-bobby-scott-va'],
['Rep. Randy Forbes [R, VA-4]', 'rep-randy-forbes-va'],
['Rep. Robert Hurt [R, VA-5]', 'rep-robert-hurt-va'],
['Rep. Robert Goodlatte [R, VA-6]', 'rep-bob-goodlatte-va'],
['Rep. Eric Cantor [R, VA-7]', 'rep-eric-cantor-va'],
['Rep. James Moran [D, VA-8]', 'rep-jim-moran-va'],
['Rep. Morgan Griffith [R, VA-9]', 'rep-morgan-griffith-va'],
['Rep. Frank Wolf [R, VA-10]', 'rep-frank-wolf-va'],
['Rep. Gerald Connolly [D, VA-11]', 'rep-gerry-connolly-va']],

'GU': [['Del. Madeleine Bordallo [D, GU-0]', 'del-madeline-bordallo-gu']],

'CO': [['Sen. Mark Udall [D, CO]', 'sen-mark-udall-co'],
['Sen. Michael Bennet [D, CO]', 'sen-michael-bennet-co'],
['Rep. Diana DeGette [D, CO-1]', 'rep-diana-degette-co'],
['Rep. Jared Polis [D, CO-2]', 'rep-jared-polis-co'],
['Rep. Scott Tipton [R, CO-3]', 'rep-scott-tipton-co'],
['Rep. Cory Gardner [R, CO-4]', 'rep-cory-gardner-co'],
['Rep. Doug Lamborn [R, CO-5]', 'rep-doug-lamborn-co'],
['Rep. Mike Coffman [R, CO-6]', 'rep-mike-coffman-co'],
['Rep. Ed Perlmutter [D, CO-7]', 'rep-ed-perlmutter-co']],

'VI': [['Del. Donna Christensen [D, VI-0]', 'del-donna-christensen-vi']],

'CA': [['Sen. Barbara Boxer [D, CA]', 'sen-barbara-boxer-ca'],
['Sen. Dianne Feinstein [D, CA]', 'sen-dianne-feinstein-ca'], 
['Rep. Doug LaMalfa[R, CA-1]', 'rep-doug-lamalfa-ca'],
['Rep. Jared Huffman [D, CA-2]', 'rep-jared-huffman-ca'],
['Rep. John Garamendi [D, CA-3]', 'rep-john-garamendi-ca'],
['Rep. Tom McClintock [R, CA-4]', 'rep-tom-mcclintock-ca'],
['Rep. Mike Thompson [D, CA-5]', 'rep-mike-thompson-ca'],
['Rep. Doris Matsui [D, CA-6]', 'rep-doris-matsui-ca'],
['Rep. Ami Bera [D, CA-7]', 'rep-ami-bera-ca'],
['Rep. Paul Cook [R, CA-8]', 'rep-paul-cook-ca'],
['Rep. Jerry McNerney [D, CA-9]', 'rep-jerry-mcnerney-ca'],

['Rep. Jeff Denham [R, CA-10]', 'rep-jeff-denham-ca'],
['Rep. George Miller [D, CA-11]', 'rep-george-miller-ca'],
['Rep. Nancy Pelosi [D, CA-12]', 'rep-nancy-pelosi-ca'],
['Rep. Barbara Lee [D, CA-13]', 'rep-barbara-lee-ca'],
['Rep. Jackie Speier [D, CA-14]', 'rep-jackie-speier-ca'],
['Rep. Michael Honda [D, CA-17]', 'rep-mike-honda-ca'],
['Rep. Eric Swalwell [D, CA-15]', 'rep-eric-swalwell-ca'],
['Rep. Sam Farr [D, CA-20]', 'rep-sam-farr-ca'],
['Rep. Jim Costa [D, CA-16]', 'rep-jim-costa-ca'],
['Rep. Zoe Lofgren [D, CA-19]', 'rep-zoe-lofgren-ca'],

['Rep. Anna Eshoo [D, CA-18]', 'rep-anna-eshoo-ca'],
['Rep. Devin Nunes [R, CA-22]', 'rep-devin-nunes-ca'],
['Rep. Kevin McCarthy [R, CA-23]', 'rep-kevin-mccarthy-ca'],
['Rep. Lois Capps [D, CA-24]', 'rep-lois-capps-ca'],
['Rep. David Valadao [R, CA-21]', 'rep-david-valadao-ca'],
['Rep. Julia Brownley [R, CA-26]', 'rep-julia-brownley-ca'],
['Rep. Tony Cardenas [R, CA-29]', 'rep-tony-cardenas-ca'],
['Rep. Brad Sherman [D, CA-30]', 'rep-brad-sherman-ca'],
['Rep. Gloria Negrete McLeod [D, CA-35]', 'rep-gloria-negrete-mcleod-ca'],
['Rep. Adam Schiff [D, CA-28]', 'rep-adam-schiff-ca'],

['Rep. Henry Waxman [D, CA-33]', 'rep-henry-waxman-ca'],
['Rep. Xavier Becerra [D, CA-34]', 'rep-xavier-becerra-ca'],
['Rep. Judy Chu [D, CA-27]', 'rep-judy-chu-ca'],
['Rep. Karen Bass [D, CA-37]', 'rep-karen-bass-ca'],
['Rep. Lucille Roybal-Allard [D, CA-40]', 'rep-lucille-roybal-allard-ca'],
['Rep. Maxine Waters [D, CA-43]', 'rep-maxine-waters-ca'],
['Rep. Janice Hahn [D, CA-44]', 'rep-janice-hahn-ca'],
['Rep. Raul Ruiz [D, CA-36]', 'rep-raul-ruiz-ca'],
['Rep. Grace Napolitano [D, CA-32]', 'rep-grace-napolitano-ca'],
['Rep. Linda Sánchez [D, CA-38]', 'rep-linda-sanchez-ca'],

['Rep. Edward Royce [R, CA-39]', 'rep-ed-royce-ca'],
['Rep. Buck McKeon [R, CA-25]', 'rep-buck-mckeon-ca'],
['Rep. Gary Miller [R, CA-31]', 'rep-gary-miller-ca'],
['Rep. Alan Lowenthal [D, CA-47]', 'rep-alan-lowenthal-ca'],
['Rep. Ken Calvert [R, CA-42]', 'rep-ken-calvert-ca'],
['Rep. Dana Rohrabacher [R, CA-48]', 'rep-dana-rohrabacher-ca'],
['Rep. Mark Takano [D, CA-41]', 'rep-mark-takano-ca'],
['Rep. Loretta Sanchez [D, CA-46]', 'rep-loretta-sanchez-ca'],
['Rep. John Campbell [R, CA-45]', 'rep-john-campbell-ca'],
['Rep. Darrell Issa [R, CA-49]', 'rep-darrell-issa-ca'],

['Rep. Scott Peters [D, CA-52]', 'rep-scott-peters-ca'],
['Rep. Juan Vargas [D, CA-51]', 'rep-juan-vargas-ca'],
['Rep. Duncan Hunter [R, CA-50]', 'rep-duncan-hunter-ca'],
['Rep. Susan Davis [D, CA-53]', 'rep-susan-davis-ca']],
'AL': [['Sen. Jefferson Sessions [R, AL]', 'sen-jeff-sessions-al'],
['Sen. Richard Shelby [R, AL]', 'sen-richard-shelby-al'],
['Rep. Jo Bonner [R, AL-1]', 'rep-jo-bonner-al'],
['Rep. Martha Roby [R, AL-2]', 'rep-martha-roby-al'],
['Rep. Michael Rogers [R, AL-3]', 'rep-mike-rogers-al'],
['Rep. Robert Aderholt [R, AL-4]', 'rep-robert-aderholt-al'],
['Rep. Mo Brooks [R, AL-5]', 'rep-mo-brooks-al'],
['Rep. Spencer Bachus [R, AL-6]', 'rep-spencer-bachus-al'],
['Rep. Terri Sewell [D, AL-7]', 'rep-terri-sewell-al']],

'AS': [['Del. Eni Faleomavaega [D, AS-0]', 'del-eni-faleomavaega-as']],

'AR': [['Sen. Mark Pryor [D, AR]', 'sen-mark-pryor-ar'],
['Sen. John Boozman [R, AR]', 'sen-john-boozman-ar'],
['Rep. Rick Crawford [R, AR-1]', 'rep-rick-crawford-ar'],
['Rep. Tim Griffin [R, AR-2]', 'rep-tim-griffin-ar'],
['Rep. Steve Womack [R, AR-3]', 'rep-steve-womack-ar'],
['Rep. Tom Cotton [R, AR-4]', 'rep-tom-cotton-ar']],

'VT': [['Sen. Patrick Leahy [D, VT]', 'sen-patrick-leahy-vt'],
['Sen. Bernard Sanders [I, VT]', 'sen-bernie-sanders-vt'],
['Rep. Peter Welch [D, VT-0]', 'rep-peter-welch-vt']],

'IL': [['Sen. Richard Durbin [D, IL]', 'sen-dick-durbin-il'],
['Sen. Mark Kirk [R, IL]', 'sen-mark-kirk-il'],
['Rep. Bobby Rush [D, IL-1]', 'rep-bobby-rush-il'],
['Vacant [D, IL-2]', 'rep-jesse-jackson-il'],
['Rep. Daniel Lipinski [D, IL-3]', 'rep-daniel-lipinski-il'],
['Rep. Luis Gutiérrez [D, IL-4]', 'rep-luis-gutierrez-il'],
['Rep. Mike Quigley [D, IL-5]', 'rep-mike-quigley-il'],
['Rep. Peter Roskam [R, IL-6]', 'rep-peter-roskam-il'],
['Rep. Danny Davis [D, IL-7]', 'rep-danny-davis-il'],
['Rep. Tammy Duckworth [D, IL-8]', 'rep-tammy-duckworth-il'],
['Rep. Janice Schakowsky [D, IL-9]', 'rep-jan-schakowsky-il'],
['Rep. Brad Schneider [D, IL-10]', 'rep-brad-schneider-il'],
['Rep. Bill Foster [D, IL-11]', 'rep-bill-foster-il'],
['Rep. William Enyart [D, IL-12]', 'rep-william-enyart-il'],
['Rep. Rodney Davis [R, IL-13]', 'rep-rodney-davis-il'],
['Rep. Randy Hultgren [R, IL-14]', 'rep-randy-hultgren-il'],
['Rep. John Shimkus [R, IL-15]', 'rep-john-shimkus-il'],
['Rep. Adam Kinzinger [R, IL-16]', 'rep-adam-kinzinger-il'],
['Rep. Cheri Bustos [D, IL-17]', 'rep-cheri-bustos-il'],
['Rep. Aaron Schock [R, IL-18]', 'rep-aaron-schock-il']], 

'GA': [['Sen. Saxby Chambliss [R, GA]', 'sen-saxby-chambliss-ga'],
['Sen. John Isakson [R, GA]', 'sen-johnny-isakson-ga'],
['Rep. Jack Kingston [R, GA-1]', 'rep-jack-kingston-ga'],
['Rep. Sanford Bishop [D, GA-2]', 'rep-sanford-bishop-ga'],
['Rep. Lynn Westmoreland [R, GA-3]', 'rep-lynn-westmoreland-ga'],
['Rep. Henry Johnson [D, GA-4]', 'rep-hank-johnson-ga'],
['Rep. John Lewis [D, GA-5]', 'rep-john-lewis-ga'],
['Rep. Tom Price [R, GA-6]', 'rep-tom-price-ga'],
['Rep. Rob Woodall [R, GA-7]', 'rep-rob-woodall-ga'],
['Rep. Austin Scott [R, GA-8]', 'rep-james-scott-ga'],
['Rep. Doug Collins [R, GA-9]', 'rep-doug-collins-ga'],
['Rep. Paul Broun [R, GA-10]', 'rep-paul-broun-ga'],
['Rep. John Gingrey [R, GA-11]', 'rep-phil-gingrey-ga'],
['Rep. John Barrow [D, GA-12]', 'rep-john-barrow-ga'],
['Rep. David Scott [D, GA-13]', 'rep-david-scott-ga'],
['Rep. Tom Graves [R, GA-14]', 'rep-tom-graves-ga']], 

'IN': [['Sen. Joe Donnelly [D, IN]', 'sen-joe-donnelly-in'],
['Sen. Daniel Coats [R, IN]', 'sen-dan-coats-in'],
['Rep. Susan Brooks [R, IN-5]', 'rep-susan-brooks-in'],
['Rep. Luke Messer [R, IN-6]', 'rep-luke-messer-in'],
['Rep. Peter Visclosky [D, IN-1]', 'rep-pete-visclosky-in'],
['Rep. Jackie Walorski [R, IN-2]', 'rep-jackie-walorski-in'],
['Rep. Andr&eacut Carson [D, IN-7]', 'rep-andre-carson-in'],
['Rep. Marlin Stutzman [R, IN-3]', 'rep-marlin-stutzman-in'],
['Rep. Todd Rokita [R, IN-4]', 'rep-todd-rokita-in'],
['Rep. Larry Bucshon [R, IN-8]', 'rep-larry-bucshon-in'],
['Rep. Todd Young [R, IN-9]', 'rep-todd-young-in']],

'IA': [['Sen. Charles Grassley [R, IA]', 'sen-chuck-grassley-ia'],
['Sen. Thomas Harkin [D, IA]', 'sen-tom-harkin-ia'],
['Rep. Bruce Braley [D, IA-1]', 'rep-bruce-braley-ia'],
['Rep. David Loebsack [D, IA-2]', 'rep-dave-loebsack-ia'],
['Rep. Thomas Latham [R, IA-3]', 'rep-tom-latham-ia'],
['Rep. Steve King [R, IA-4]', 'rep-steve king-ia']],

'KS': [['Sen. Pat Roberts [R, KS]', 'sen-pat-roberts-ks'],
['Sen. Jerry Moran [R, KS]', 'sen-jerry-moran-ks'],
['Rep. Tim Huelskamp [R, KS-1]','rep-tim-huelskamp-ks'],
['Rep. Lynn Jenkins [R, KS-2]','rep-lynn-jenkins-ks'],
['Rep. Kevin Yoder [R, KS-3]','rep-kevin-yoder-ks'],
['Rep. Mike Pompeo [R, KS-4]','rep-mike-pompeo-ks']],

'MA': [['Sen. Mo Cowan [D, MA]', 'sen-mo-cowan-ma'],
['Sen. Elizabeth Warren [D, MA]', 'sen-elizabeth-warren-ma'],
['Rep. Joe Kennedy [D, MA-4]', 'rep-joe-kennedy-ma'],
['Rep. Stephen Lynch [D, MA-8]', 'rep-stephen-lynch-ma'],
['Rep. Edward Markey [D, MA-5]', 'rep-ed-markey-ma'],
['Rep. James McGovern [D, MA-2]', 'rep-jim-mcgovern-ma'],
['Rep. Richard Neal [D, MA-1]', 'rep-richard-neal-ma'],
['Rep. John Tierney [D, MA-6]', 'rep-john-tierney-ma'],
['Rep. Niki Tsongas [D, MA-3]', 'rep-niki-tsongas-ma'],
['Rep. William Keating [D, MA-9]', 'rep-bill-keating-ma'],
['Rep. Mike Capuano [D, MA-7]', 'rep-mike-capuano-ma']],

'AZ': [['Sen. Jeff Flake [R, AZ]', 'sen-jeff-flake-az'],
['Sen. John McCain [R, AZ]', 'sen-john-mccain-az'],
['Rep. Paul Gosar [R, AZ-4]', 'rep-paul-gosar-az'],
['Rep. Trent Franks [R, AZ-8]', 'rep-trent-franks-az'],
["Rep. Raul Grijalva [D, AZ-3]", 'rep-raul-grijalva-az'],
['Rep. Ann Kirkpatrick [D, AZ-1]', 'rep-ann-kirkpatrick-az'],
['Rep. David Schweikert [R, AZ-6]', 'rep-david-schweikert-az'],
['Rep. Ron Barber [D, AZ-2]', 'rep-ron-barber-az'],
['Rep. Matt Salmon [R, AZ-5]', 'rep-matt-salmon-az'],
['Rep. Ed Pastor [D, AZ-7]', 'rep-ed-pastor-az'],
['Rep. Kyrsten Sinema [D, AZ-9]', 'rep-kyrsten-sinema-az']], 

'ID': [['Sen. Michael Crapo [R, ID]', 'sen-mike-crapo-id'],
['Sen. James Risch [R, ID]', 'sen-jim-risch-id'],
['Rep. Michael Simpson [R, ID-2]', 'rep-mike-simpson-id'],
['Rep. Raúl Labrador [R, ID-1]', 'rep-raul-labrador-id']],

'CT': [['Sen. Chris Murphy [D, CT]', 'sen-chris-murphy-ct'],
['Sen. Richard Blumenthal [D, CT]', 'sen-richard-blumenthal-ct'],
['Rep. John Larson [D, CT-1]', 'rep-john-larson-ct'],
['Rep. Joe Courtney [D, CT-2]', 'rep-joe-courtney-ct'],
['Rep. Rosa DeLauro [D, CT-3]', 'rep-rosa-delauro-ct'],
['Rep. James Himes [D, CT-4]', 'rep-jim-himes-ct'],
['Rep. Elizabeth Esty [D, CT-5]', 'rep-elizabeth-esty-ct']],

'ME': [['Sen. Susan Collins [R, ME]', 'sen-susan-collins-me'],
['Sen. Angus King [I, ME]', 'sen-angus-king-me'],
['Rep. Michael Michaud [D, ME-2]', 'rep-mike-michaud-me'],
['Rep. Chellie Pingree [D, ME-1]', 'rep-chellie-pingree-me']],
'MD': [['Sen. Barbara Mikulski [D, MD]', 'sen-barbara-mikulski-md'],

['Sen. Benjamin Cardin [D, MD]', 'sen-ben-cardin-md'],
['Rep. Andy Harris [R, MD-1]', 'rep-andy-harris-md'],
['Rep. Dutch Ruppersberger [D, MD-2]', 'rep-dutch-ruppersberger-md'],
['Rep. John Sarbanes [D, MD-3]', 'rep-john-sarbanes-md'],
['Rep. Donna Edwards [D, MD-4]', 'rep-donna-edwards-md'],
['Rep. Steny Hoyer [D, MD-5]', 'rep-steny-hoyer-md'],
['Rep. John Delaney [D, MD-6]', 'rep-john-delaney-md'],
['Rep. Elijah Cummings [D, MD-7]', 'rep-elijah-cummings-md'],
['Rep. Christopher Van Hollen [D, MD-8]', 'rep-chris-van-hollen-md']], 

'OK': [['Sen. James Inhofe [R, OK]', 'sen-james-inhofe-ok'],
['Sen. Thomas Coburn [R, OK]', 'sen-tom-coburn-ok'],
['Rep. Tom Cole [R, OK-4]', 'rep-tom-cole-ok'],
['Rep. Frank Lucas [R, OK-3]', 'rep-frank-lucas-ok'],
['Rep. Jim Bridenstine [R, OK-1]', 'rep-jim-bridenstine-ok'],
['Rep. Markwayne Mullin [R, OK-2]', 'rep-markwayne-mullin-ok'],
['Rep. James Lankford [R, OK-5]', 'rep-james-lankford-ok']],

'OH': [['Sen. Sherrod Brown [D, OH]', 'sen-sherrod-brown-oh'],
['Sen. Robert Portman [R, OH]', 'sen-rob-portman-oh'],
['Rep. Steven Chabot [R, OH-1]', 'rep-steve-chabot-oh'],
['Rep. Brad Wenstrup [R, OH-2]', 'rep-brad-wenstrup-oh'],
['Rep. Joyce Beatty [D, OH-3]', 'rep-joyce-beatty-oh'],
['Rep. Jim Jordan [R, OH-4]', 'rep-jim-jordan-oh'],
['Rep. Robert Latta [R, OH-5]', 'rep-bob-latta-oh'],
['Rep. Bill Johnson [R, OH-6]', 'rep-bill-johnson-oh'],
['Rep. Bob Gibbs [R, OH-7]', 'rep-bob-gibbs-oh'],
['Rep. John Boehner [R, OH-8]', 'rep-john-boehner-oh'],
['Rep. Marcy Kaptur [D, OH-9]', 'rep-marcy-kaptur-oh'],
['Rep. Mike Turner [R, OH-10]', 'rep-mike-turner-oh'],
['Rep. Marcia Fudge [D, OH-11]', 'rep-marcia-fudge-oh'],
['Rep. Patrick Tiberi [R, OH-12]', 'rep-pat-tiberi-oh'],
['Rep. Tim Ryan [D, OH-13]', 'rep-tim-ryan-oh'],
['Rep. David Joyce [R, OH-14]', 'rep-david-joyce-oh'],
['Rep. Steve Stivers [R, OH-15]', 'rep-steven-stivers-oh'],
['Rep. Jim Renacci [R, OH-16]', 'rep-jim-renacci-oh']],

'UT': [['Sen. Orrin Hatch [R, UT]', 'sen-orrin-hatch-ut'],
['Sen. Mike Lee [R, UT]', 'sen-mike-lee-ut'],
['Rep. Rob Bishop [R, UT-1]', 'rep-rob-bishop-ut'],
['Rep. Jim Matheson [D, UT-4]', 'rep-jim-matheson-ut'],
['Rep. Jason Chaffetz [R, UT-3]', 'rep-jason-chaffetz-ut'],
['Rep. Chris Stewart [R, UT-2]', 'rep-chris-stewart-ut']],

'MO': [['Sen. Claire McCaskill [D, MO]', 'sen-claire-mccaskill-mo'],
['Sen. Roy Blunt [R, MO]', 'sen-roy-blunt-mo'],
['Rep. William Clay [D, MO-1]', 'rep-lacy-clay-mo'],
['Rep. Ann Wagner [R, MO-2]', 'rep-ann-wagner-mo'],
['Rep. Blaine Luetkemeyer [R, MO-3]', 'rep-blaine-luetkemeyer-mo'],
['Rep. Vicky Hartzler [R, MO-4]', 'rep-vicky-hartzler-mo'],
['Rep. Emanuel Cleaver [D, MO-5]', 'rep-emanuel-cleaver-mo'],
['Rep. Samuel Graves [R, MO-6]', 'rep-sam-graves-mo'],
['Rep. Billy Long [R, MO-7]', 'rep-billy-long-mo'],
['Rep. Jo Ann Emerson [R, MO-8]', 'rep-jo-ann-emerson-mo']],

'MN': [['Sen. Amy Klobuchar [D, MN]', 'sen-amy-klobuchar-mn'],
['Sen. Al Franken [D, MN]', 'sen-al-franken-mn'],
['Rep. Timothy Walz [D, MN-1]', 'rep-tim-walz-mn'],
['Rep. John Kline [R, MN-2]', 'rep-john-kline-mn'],
['Rep. Erik Paulsen [R, MN-3]', 'rep-erik-paulsen-mn'],
['Rep. Betty McCollum [D, MN-4]', 'rep-betty-mccollum-mn'],
['Rep. Keith Ellison [D, MN-5]', 'rep-keith-ellison-mn'],
['Rep. Michele Bachmann [R, MN-6]', 'rep-michele-bachmann-mn'],
['Rep. Collin Peterson [D, MN-7]', 'rep-collin-peterson-mn'],
['Rep. Rick Nolan [D, MN-8]', 'rep-rick-nolan-mn']],

'MI': [['Sen. Carl Levin [D, MI]', 'sen-carl-levin-mi'],
['Sen. Debbie Ann Stabenow [D, MI]', 'sen-debbie-stabenow-mi'],
['Rep. Dan Benishek [R, MI-1]', 'rep-dan-benishek-mi'],
['Rep. Bill Huizenga [R, MI-2]', 'rep-bill-huizenga-mi'],
['Rep. Justin Amash [R, MI-3]', 'rep-justin-amash-mi'],
['Rep. David Camp [R, MI-4]', 'rep-dave-camp-mi'],
['Rep. Dale Kildee [D, MI-5]', 'rep-dale-kildee-mi'],
['Rep. Frederick Upton [R, MI-6]', 'rep-fred-upton-mi'],
['Rep. Timothy Walberg [R, MI-7]', 'rep-tim-walberg-mi'],
['Rep. Michael Rogers [R, MI-8]', 'rep-mike-rogers-mi'],
['Rep. Gary Peters [D, MI-14]', 'rep-gary-peters-mi'],
['Rep. Candice Miller [R, MI-10]', 'rep-candice-miller-mi'],
['Rep. Kerry Bentivolio [R, MI-11]', 'rep-kerry-bentivolio-mi'],
['Rep. Sander Levin [D, MI-9]', 'rep-sandy-levin-mi'],
['Rep. John Conyers [D, MI-13]', 'rep-john-conyers-mi'],
['Rep. John Dingell [D, MI-12]', 'rep-john-dingell-mi']],

'RI': [['Sen. John Reed [D, RI]', 'sen-jack-reed-ri'],
['Sen. Sheldon Whitehouse [D, RI]', 'sen-sheldon-whitehouse-ri'],
['Rep David Cicilline [D, RI-1]', 'rep-david-cicilline-ri'],
['Rep. James Langevin [D, RI-2]', 'rep-jim-langevin-ri']],
'MT': [['Sen. Max Baucus [D, MT]', 'sen-max-baucus-mt'],

['Sen. Jon Tester [D, MT]', 'sen-jon-tester-mt'],
['Rep. Steve Daines [R, MT-0]', 'rep-steve-daines-mt']],

'MP': [['Del. Gregorio Sablan [D, MP-0]', 'del-gregorio-sablan-mp']],

'MS': [['Sen. Thad Cochran [R, MS]', 'sen-thad-cochran-ms'],
['Sen. Roger Wicker [R, MS]', 'sen-roger-wicker-ms'],
['Rep. Alan Nunnelee [R, MS-1]', 'rep-alan-nunnelee-ms'],
['Rep. Bennie Thompson [D, MS-2]', 'rep-bennie-thompson-ms'],
['Rep. Gregg Harper [R, MS-3]', 'rep-gregg-harper-ms'],
['Rep. Steven Palazzo [R, MS-4]', 'rep-steven-palazzo-ms']],

'PR': [['Res.Comm. Pedro Pierluisi [D, PR-0]', 'com-pedro-pierluisi-pr']],

'SC': [['Sen. Lindsey Graham [R, SC]', 'sen-lindsey-graham-sc'],
['Sen. Tim Scott [R, SC]', 'sen-tim-scott-sc'],
['Vacant [R, SC-1]', 'rep-tim-scott-sc'],
['Rep. Addison Wilson [R, SC-2]', 'rep-joe-wilson-sc'],
['Rep. Jeff Duncan [R, SC-3]', 'rep-jeff-duncan-sc'],
['Rep. Trey Gowdy [R, SC-4]', 'rep-trey-gowdy-sc'],
['Rep. Mick Mulvaney [R, SC-5]', 'rep-mick-mulvaney-sc'],
['Rep. James Clyburn [D, SC-6]', 'rep-james-clyburn-sc'],
['Rep. Tom Rice [R, SC-7]', 'rep-tom-rice-sc']],

'KY': [['Sen. Mitch McConnell [R, KY]', 'sen-mitch-mcconnell-ky'],
['Sen. Rand Paul [R, KY]', 'sen-rand-paul-ky'],
['Rep. Edward Whitfield [R, KY-1]', 'rep-ed-whitfield-ky'],
['Rep. Brett Guthrie [R, KY-2]', 'rep-steven-guthrie-ky'],
['Rep. John Yarmuth [D, KY-3]', 'rep-john-yarmuth-ky'],
['Rep. Thomas Massie [R, KY-4]', 'rep-thomas-massie-ky'],
['Rep. Harold Rogers [R, KY-5]', 'rep-hal-rogers-ky'],
['Rep. Andy Barr [R, KY-6]', 'rep-andy-barr-ky']],

'OR': [['Sen. Ron Wyden [D, OR]', 'sen-ron-wyden-or'],
['Sen. Jeff Merkley [D, OR]', 'sen-jeff-merkley-or'],
['Rep. Suzanne Bonamici [D, OR-1]', 'rep-suzanne-bonamici-or'],
['Rep. Greg Walden [R, OR-2]', 'rep-greg-walden-or'],
['Rep. Earl Blumenauer [D, OR-3]', 'rep-earl-blumenauer-or'],
['Rep. Peter DeFazio [D, OR-4]', 'rep-peter-defazio-or'],
['Rep. Kurt Schrader [D, OR-5]', 'rep-kurt-schrader-or']],

'SD': [['Sen. Tim Johnson [D, SD]', 'sen-tim-johnson-sd'],
['Sen. John Thune [R, SD]', 'sen-john-thune-sd'],
['Rep. Kristi Noem [R, SD-0]', 'rep-kristi-noem-sd']]};

	function dist_update(hashchange) {
		// Update district dropdown list options and make sure that
		// report_district is a valid value for the current state.
		$('#dist_options_district').html("");
		if (dist_report_state == "") {
			dist_report_district = 0;
			$('#dist_options_district').hide();
		} else if (memurls[dist_report_state].length <= 3) {
			$('#dist_options_district').
				append($("<option></option>").
					attr("value", 0).
					text("All"));
			dist_report_district = 0;
			hashchange= true;
		} else {
			$('#dist_options_district').show();
			if (dist_report_district == 0){
				dist_report_district = "";
			}
			if (dist_report_district > memurls[dist_report_state].length) {
				dist_report_district = 1;
			}
				$('#dist_options_district').
					append($("<option></option>").
						attr("value", 0).
						attr("selected", 0 == dist_report_district).
						text("All")); 
			for (var i = 1; i <= memurls[dist_report_state].length -2 ; i++) {
				$('#dist_options_district').
					append($("<option></option>").
						attr("value", i).
						attr("selected", i == dist_report_district).
						text(i)); 
			}
			hashchange= true;
		}
		
		selstate = $('#dist_options_state').val()
		seldist = $('#dist_options_district').val()
		if ( seldist == 0) {
			if (selstate == "DC" || selstate == "PR") {
				$('#distgo').attr("href", "/district/" + selstate);
			} else {
				$('#distgo').attr("href", "/state/" + selstate);
			}
		} else {
			$('#distgo').attr("href", "/district/" + selstate + "/" + seldist);
		}
	}

	function mem_update(hashchange) {
		// Update district dropdown list options and make sure that
		// report_district is a valid value for the current state.
		$('#mem_options_member').html("");
		var state = $('mem_options_state').val()
		if (mem_report_member == 0){
			mem_report_member = "";
		}
		if (mem_report_member > memurls[mem_report_state].length) {
			mem_report_member = 1;
		}
		if (mem_report_state == "") {
			mem_report_member = 0;
			$('#dist_options_district').hide();
		} else {
			for (var i = 1; i <= memurls[mem_report_state].length ; i++) {
				$('#mem_options_member').
					append($("<option></option>").
						attr("value", memurls[mem_report_state][i-1][1]).
						attr("selected", memurls[mem_report_state][i-1][1] == mem_report_member).
						text(memurls[mem_report_state][i-1][0])); 
			}
			//hashchange= true;
	}

		//$('#mem_options_member').attr("selected", i == mem_report_member);
	
		selstate = $('#mem_options_state').val();
		selmem = $('#mem_options_member').val();
		$('#memgo').attr("href", "/member/" + selmem);
	}


function zoompop(id) {
	$.colorbox({
                transition: "none",
                inline: true,
                href: '#' + id,
                opacity: .5
		});
	return false;
}
