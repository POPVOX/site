./mysql_shell.sh -Be "select min(date(date_joined)), count(*) from auth_user group by year(date_joined), week(date_joined)"
