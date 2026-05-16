exports.handler = async () => ({
  statusCode: 200,
  body: JSON.stringify({
    has_url: !!process.env.SUPABASE_URL,
    has_key: !!process.env.SUPABASE_ANON_KEY,
    url_preview: (process.env.SUPABASE_URL || '').slice(0, 30)
  })
});
