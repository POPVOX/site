./mysql_shell.sh -Be "select min(date(date_joined)), count(*) from auth_user group by date(date_joined)"
