import express from 'express';
import bodyParser from 'body-parser';
import { runAnalysis } from './analysisTemplates.js';

const app = express();
app.use(bodyParser.json());

app.post('/analyze', async (req, res) => {
  try {
    const { code, params, format } = req.body;
    const result = await runAnalysis(code, params, format);
    if (typeof result === 'string' && /\.(pdf|xlsx|docx)$/.test(result)) {
      res.download(result);
    } else {
      res.json({ result });
    }
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`Analysis service on port ${PORT}`));
