wget -O - http://www.popvox.com/blog_template > template.html
perl -p -e "if (\$_ =~ /HEADER---FOOTER/) { last; }" template.html > header.php 
perl -n -e "if (\$x) { print; } if (\$_ =~ /HEADER---FOOTER/) { \$x = 1; }" template.html > footer.php
rm template.html
