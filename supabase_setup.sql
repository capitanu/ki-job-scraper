-- Create table
CREATE TABLE job_state (
  id TEXT PRIMARY KEY DEFAULT 'default',
  applied TEXT[] DEFAULT '{}',
  irrelevant TEXT[] DEFAULT '{}'
);

-- Insert initial row
INSERT INTO job_state (id) VALUES ('default');

-- Enable public access (for anon key)
ALTER TABLE job_state ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public access" ON job_state FOR ALL USING (true) WITH CHECK (true);
