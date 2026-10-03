/*
  Phase 12B-III (D25 / D26) — production SQL Server backup schedule as SQL Server Agent jobs. DEPLOYMENT TEMPLATE: not executed on the
  development machine (it has no off-host, object-locked backup store). Run with sqlcmd on the production instance, e.g.

    sqlcmd -S <instance> -E -i ops/sqlserver/backup-jobs.sql ^
           -v DB="carbon_platform" BACKUP_URL="s3://<backup-endpoint>/<backup-bucket>/carbon" CERT="<server-certificate-name>" ^
              OPERATOR="<Platform/DevOps operator name>"

  Prerequisites (docs/operations-runbook.md, "SQL Server backup"):
    - FULL recovery model on the production database (never change it; D29 applies to development only);
    - a server certificate in master for backup encryption (AES-256), with the certificate AND its private key backed up to the
      secret store (without them no backup can be restored);
    - an S3-compatible, India-region (D50), object-locked backup bucket (ops/minio/backup-and-replication.sh) and a SQL Server
      credential for it:  CREATE CREDENTIAL [s3://<backup-endpoint>/<backup-bucket>] WITH IDENTITY = 'S3 Access Key',
      SECRET = '<access-key>:<secret-key>';  (values from the secret store — never committed)
    - a SQL Agent operator for the Platform/DevOps team (D45) — create it with the team's own distribution address.

  Schedule (designed against RPO 15 min / RTO 1 h — these are targets, proven only by production restore drills):
    - LOG every 5 minutes  -> worst-case data loss ~5 min + backup duration (< RPO 15 min);
    - DIFF every 6 hours   -> a restore replays at most 6 h of log backups (bounded restore time for the RTO);
    - FULL weekly (Sunday 01:00), followed by RESTORE VERIFYONLY;
    - every backup WITH CHECKSUM, COMPRESSION, ENCRYPTION; retention 60 days enforced by the bucket's object lock + lifecycle
      (D26 / D48) — backups are never deleted by the application;
    - msdb backup history older than 60 days is cleaned daily.
*/
SET NOCOUNT ON;
USE msdb;
GO

DECLARE @db sysname = N'$(DB)', @url nvarchar(400) = N'$(BACKUP_URL)', @cert sysname = N'$(CERT)', @op sysname = N'$(OPERATOR)';
DECLARE @enc nvarchar(200) = N'ENCRYPTION (ALGORITHM = AES_256, SERVER CERTIFICATE = [' + @cert + N'])';
DECLARE @stamp nvarchar(200) = N'REPLACE(REPLACE(REPLACE(CONVERT(nvarchar(19), SYSUTCDATETIME(), 126), N''-'', N''''), N'':'', N''''), N''T'', N''T'')';

DECLARE @jobs TABLE (name sysname, cmd nvarchar(max), freq_type int, freq_interval int, subday_type int, subday_interval int, start_time int);
INSERT @jobs VALUES
 (N'carbon - backup FULL (weekly)',
  N'DECLARE @f nvarchar(400) = N''' + @url + N'/' + @db + N'/full/' + @db + N'_full_'' + ' + @stamp + N' + N''.bak'';
    BACKUP DATABASE [' + @db + N'] TO URL = @f WITH CHECKSUM, COMPRESSION, FORMAT, INIT, ' + @enc + N';
    RESTORE VERIFYONLY FROM URL = @f WITH CHECKSUM;', 8, 1, 1, 0, 10000),
 (N'carbon - backup DIFF (6 h)',
  N'DECLARE @f nvarchar(400) = N''' + @url + N'/' + @db + N'/diff/' + @db + N'_diff_'' + ' + @stamp + N' + N''.bak'';
    BACKUP DATABASE [' + @db + N'] TO URL = @f WITH DIFFERENTIAL, CHECKSUM, COMPRESSION, FORMAT, INIT, ' + @enc + N';
    RESTORE VERIFYONLY FROM URL = @f WITH CHECKSUM;', 4, 1, 8, 6, 0),
 (N'carbon - backup LOG (5 min)',
  N'DECLARE @f nvarchar(400) = N''' + @url + N'/' + @db + N'/log/' + @db + N'_log_'' + ' + @stamp + N' + N''.trn'';
    BACKUP LOG [' + @db + N'] TO URL = @f WITH CHECKSUM, COMPRESSION, FORMAT, INIT, ' + @enc + N';', 4, 1, 4, 5, 0),
 (N'carbon - backup history cleanup (60 days)',
  N'DECLARE @before datetime = DATEADD(day, -60, GETDATE()); EXEC msdb.dbo.sp_delete_backuphistory @oldest_date = @before;', 4, 1, 1, 0, 30000);

DECLARE @name sysname, @cmd nvarchar(max), @ft int, @fi int, @st int, @si int, @start int;
DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT name, cmd, freq_type, freq_interval, subday_type, subday_interval, start_time FROM @jobs;
OPEN c;
FETCH NEXT FROM c INTO @name, @cmd, @ft, @fi, @st, @si, @start;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = @name) EXEC msdb.dbo.sp_delete_job @job_name = @name;
    EXEC msdb.dbo.sp_add_job @job_name = @name, @enabled = 1, @notify_level_email = 2, @notify_email_operator_name = @op,
         @description = N'Phase 12B-III D26 backup schedule (docs/operations-runbook.md). Failure alerts go to Platform/DevOps.';
    EXEC msdb.dbo.sp_add_jobstep @job_name = @name, @step_name = N'run', @subsystem = N'TSQL', @database_name = N'master',
         @command = @cmd, @retry_attempts = 2, @retry_interval = 1;
    EXEC msdb.dbo.sp_add_jobschedule @job_name = @name, @name = @name, @freq_type = @ft, @freq_interval = @fi,
         @freq_subday_type = @st, @freq_subday_interval = @si, @active_start_time = @start;
    EXEC msdb.dbo.sp_add_jobserver @job_name = @name;
    FETCH NEXT FROM c INTO @name, @cmd, @ft, @fi, @st, @si, @start;
END
CLOSE c;
DEALLOCATE c;
GO
