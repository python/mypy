// Executed exclusively from the default branch, with PR artifacts treated as data.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const MARKER = '<!-- mypyc-primer -->';
const SHA = /^[0-9a-f]{40}$/;
const NAME = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const MAX_JSON = 512 * 1024;
const MAX_COMMENT = 50000;

function validateManifest(manifest, run) {
  if (manifest.version !== 1 || !Number.isSafeInteger(manifest.pr_number) ||
      manifest.pr_number <= 0 || manifest.head_sha !== run.head_sha ||
      !SHA.test(manifest.head_sha) || !SHA.test(manifest.base_sha) ||
      typeof manifest.base_ref !== 'string' || !manifest.base_ref.length ||
      manifest.base_ref.length > 1024 || /[\s\x00-\x1f\x7f]/.test(manifest.base_ref) ||
      manifest.run_id !== String(run.id) || !Number.isSafeInteger(manifest.run_attempt) ||
      manifest.run_attempt < 1 || manifest.run_attempt > run.run_attempt ||
      !Array.isArray(manifest.projects) || !manifest.projects.length ||
      manifest.projects.length > 100) {
    throw new Error('Invalid mypyc primer manifest or workflow association');
  }
  const names = new Set();
  for (const project of manifest.projects) {
    if (typeof project.name !== 'string' || !NAME.test(project.name) ||
        typeof project.python_version !== 'string' || !/^3\.\d+$/.test(project.python_version) ||
        names.has(project.name)) {
      throw new Error('Invalid or duplicate project in manifest');
    }
    names.add(project.name);
  }
}

function validateResult(result, project, manifest) {
  if (result.version !== 1 || result.name !== project.name ||
      result.python_version !== project.python_version ||
      result.head_sha !== manifest.head_sha || result.base_sha !== manifest.base_sha ||
      !(result.project_sha === null || SHA.test(result.project_sha))) {
    throw new Error(`Invalid result for ${project.name}`);
  }
  for (const attempt of [result.head, result.base]) {
    if (attempt !== null && (typeof attempt !== 'object' ||
        !['passed', 'failed', 'error'].includes(attempt.status) ||
        !['setup', 'compiler', 'build', 'compiled-import', 'test'].includes(attempt.stage) ||
        typeof attempt.tail !== 'string')) {
      throw new Error(`Invalid attempt for ${project.name}`);
    }
  }
  if (!result.head || (result.head.status === 'passed' &&
      (result.base !== null || !SHA.test(result.project_sha)))) {
    throw new Error(`Incomplete result for ${project.name}`);
  }
}

function fencedTail(tail, limit) {
  // ANSI/control sequences don't belong in a comment; the full Actions log is linked.
  let text = tail.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '')
    .replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '').split('\n').slice(-20).join('\n');
  if (text.length > limit) text = '[excerpt truncated]\n' + text.slice(Math.max(0, text.length - limit));
  const longest = Math.max(2, ...Array.from(text.matchAll(/`+/g), m => m[0].length));
  const fence = '`'.repeat(longest + 1);
  return `${fence}text\n${text}\n${fence}`;
}

function projectLogLinks(projects, jobs, runUrl, runAttempt = Infinity) {
  const links = new Map();
  for (const project of projects) {
    const name = `Compile and test (${project.name}, ${project.python_version})`;
    // Include older attempts: a failed-jobs rerun reuses other projects' results.
    const job = jobs.filter(job => job.name === name && job.run_attempt <= runAttempt)
      .sort((a, b) => b.run_attempt - a.run_attempt || b.id - a.id)[0];
    if (!job) continue;
    const attempts = {};
    for (const [attempt, stepName] of [
      ['head', 'Compile and test with PR mypyc'],
      ['base', 'Compile and test with target branch mypyc'],
    ]) {
      const step = job.steps.find(step => step.name === stepName && step.conclusion !== 'skipped');
      if (step) attempts[attempt] = `${runUrl}/job/${job.id}#step:${step.number}:1`;
    }
    links.set(project.name, attempts);
  }
  return links;
}

function renderComment(manifest, results, logs, runUrl, conclusion) {
  const metadata = `${MARKER}<!-- mypyc-primer-run: ${manifest.run_id}:${manifest.run_attempt} -->`;
  if (conclusion === 'success' && manifest.projects.length &&
      manifest.projects.every(project => results.get(project.name)?.head.status === 'passed')) {
    return `${metadata}mypyc primer: all configured projects compiled and passed their tests. ✅`;
  }
  const blocks = [metadata, '## mypyc primer detected failures ❌'];
  // Branch names can contain backticks; keep the entire name inside a code span.
  const branchFence = '`'.repeat(Math.max(0,
    ...Array.from((manifest.base_ref || '').matchAll(/`+/g), m => m[0].length)) + 1);
  // Shared run information appears inside the first failure's details only.
  const context = [
    `PR commit: \`${manifest.head_sha}\``,
    ...(manifest.base_ref ? [`Target branch: ${branchFence} ${manifest.base_ref} ${branchFence}`] : []),
    ...(manifest.base_sha ? [`Target branch commit: \`${manifest.base_sha}\``] : []),
    `[Workflow run](${runUrl})`,
    ...(conclusion !== 'success' ? [`Workflow conclusion: ${conclusion}`] : []),
  ];
  // Leave space for all project headings and links even with a large catalog.
  const excerpts = new Map();
  for (const project of manifest.projects) {
    const result = results.get(project.name);
    if (result?.head.status === 'passed') continue;
    const log = logs.get(project.name);
    const prLink = log?.head ? `[PR log](${log.head})` : null;
    const baseLink = log?.base ? `[Target branch log](${log.base})` : null;
    const details = [`Python: ${project.python_version}`,
      ...(result?.project_sha ? [`Project revision: \`${result.project_sha}\``] : [])];
    let heading;
    if (!result || result.head.status === 'error' || result.base?.status === 'error' ||
        (result.head.status === 'failed' && (!result.base || !prLink || !baseLink))) {
      const base = result?.base?.status;
      const baseStatus = base === 'passed' ? 'target branch succeeded'
        : base === 'failed' ? 'target branch failed' : 'target branch result unknown';
      heading = `Check incomplete (${baseStatus})`;
      details.push('Compilation and test results could not be confirmed.');
      const links = [prLink, baseLink].filter(Boolean);
      if (links.length) details.push(links.join(' · '));
    } else if (result.base.status === 'failed') {
      heading = 'Failed both on PR and target branch';
      details.push(`${prLink} · ${baseLink}`);
    } else {
      heading = 'Failed on PR and succeeded on target branch';
      const placeholder = `<!-- excerpt-${project.name} -->`;
      excerpts.set(placeholder, result.head.tail);
      details.push(prLink, `Last 20 lines of the PR log:\n\n${placeholder}`);
    }
    details.push(...context.splice(0));
    blocks.push(`### ${project.name}: ${heading}\n\n<details>\n<summary>Details</summary>\n\n${details.join('\n\n')}\n\n</details>`);
  }
  if (blocks.length === 2) {
    blocks.push(`### CI checks did not complete\n\n<details>\n<summary>Details</summary>\n\nCompilation and test results could not be confirmed.\n\n${context.join('\n\n')}\n\n</details>`);
  }
  let body = blocks.join('\n\n');
  // A fence may be as long as its contents, so reserve up to three characters
  // of Markdown for each excerpt character. Headings and log links stay intact.
  const limit = Math.min(6000, Math.max(0,
    Math.floor((MAX_COMMENT - body.length - 100 * excerpts.size) / (3 * excerpts.size))));
  body = body.replace(/<!-- excerpt-[a-z0-9_-]+ -->/g,
    placeholder => fencedTail(excerpts.get(placeholder), limit));
  if (body.length > MAX_COMMENT) throw new Error('Result comment exceeds GitHub size limit');
  return body;
}

async function readArtifact(github, repo, artifact, filename, directory) {
  if (!artifact || artifact.expired || artifact.size_in_bytes > MAX_JSON) {
    throw new Error(`Missing, expired, or oversized ${filename} artifact`);
  }
  const download = await github.rest.actions.downloadArtifact({
    ...repo, artifact_id: artifact.id, archive_format: 'zip',
  });
  const data = Buffer.from(download.data);
  if (data.length > MAX_JSON) throw new Error('Artifact download exceeds size limit');
  const archive = path.join(directory, `${artifact.id}.zip`);
  fs.writeFileSync(archive, data);
  // Read just the expected JSON member. No archive paths are extracted to disk.
  return JSON.parse(execFileSync('unzip', ['-p', archive, filename], {
    encoding: 'utf8', maxBuffer: MAX_JSON, timeout: 10000,
  }));
}

async function associatedPullRequests(github, repo, run) {
  if (run.pull_requests.length) return run.pull_requests;
  // Fork runs can omit this array, and unmerged fork commits may have no
  // commit-to-PR association. Resolve the trusted run's repository and branch.
  if (!run.head_repository) return [];
  const prs = await github.paginate(github.rest.pulls.list, {
    ...repo, state: 'all',
    head: `${run.head_repository.owner.login}:${run.head_branch}`, per_page: 100,
  });
  return prs.filter(pr => pr.head.repo?.id === run.head_repository.id &&
    pr.head.ref === run.head_branch);
}

async function publish({ github, context }, prNumber, body) {
  const repo = context.repo;
  const comments = await github.paginate(github.rest.issues.listComments, {
    ...repo, issue_number: prNumber, per_page: 100,
  });
  const runMarker = body.match(/<!-- mypyc-primer-run: \d+:\d+ -->/)?.[0];
  if (!runMarker) throw new Error('Missing workflow run marker in comment');
  if (comments.some(c => c.user.type === 'Bot' && c.body?.startsWith(MARKER) &&
      c.body.includes(runMarker))) return;
  const { data: posted } = await github.rest.issues.createComment({
    ...repo, issue_number: prNumber, body,
  });
  for (const previous of comments) {
    if (previous.user.type === 'Bot' && previous.user.login === posted.user.login &&
        previous.body?.startsWith(MARKER)) {
      await github.graphql(`mutation($id: ID!) {
        minimizeComment(input: {subjectId: $id, classifier: OUTDATED}) {
          minimizedComment { isMinimized }
        }
      }`, { id: previous.node_id });
    }
  }
}

async function comment({ github, context, core }) {
  const run = context.payload.workflow_run;
  const repo = context.repo;
  if (run.event !== 'pull_request' || run.conclusion === 'cancelled') return;
  const artifacts = new Map((await github.paginate(github.rest.actions.listWorkflowRunArtifacts, {
    ...repo, run_id: run.id, per_page: 100,
  })).filter(a => !a.expired).map(a => [a.name, a]));
  if (!artifacts.has('mypyc-primer-manifest') && run.conclusion === 'success') {
    // Eligibility discovery intentionally skipped this PR.
    return;
  }
  const associated = await associatedPullRequests(github, repo, run);
  const directory = fs.mkdtempSync(path.join(process.env.RUNNER_TEMP || os.tmpdir(), 'mypyc-primer-'));
  try {
    let manifest;
    if (artifacts.has('mypyc-primer-manifest')) {
      manifest = await readArtifact(github, repo, artifacts.get('mypyc-primer-manifest'), 'manifest.json', directory);
      validateManifest(manifest, run);
      // A failed-jobs rerun reuses the original discovery job and snapshot.
      manifest.run_attempt = run.run_attempt;
    } else {
      if (associated.length !== 1) throw new Error('Cannot associate incomplete run with a PR');
      manifest = { pr_number: associated[0].number, head_sha: run.head_sha,
        run_id: String(run.id), run_attempt: run.run_attempt, projects: [] };
    }
    if (!associated.some(pr => pr.number === manifest.pr_number)) {
      throw new Error('Manifest PR does not belong to the triggering workflow run');
    }
    const { data: pr } = await github.rest.pulls.get({ ...repo, pull_number: manifest.pr_number });
    if (pr.state !== 'open' || pr.head.sha !== manifest.head_sha ||
        (manifest.base_ref && pr.base.ref !== manifest.base_ref)) {
      core.info('Skipping closed PR or results for an older PR head or target branch');
      return;
    }
    const runUrl = `https://github.com/${repo.owner}/${repo.repo}/actions/runs/${run.id}`;
    const jobs = manifest.projects.length ? await github.paginate(github.rest.actions.listJobsForWorkflowRun, {
      ...repo, run_id: run.id, filter: 'all', per_page: 100,
    }) : [];
    const logs = projectLogLinks(manifest.projects, jobs, runUrl, run.run_attempt);
    const results = new Map();
    for (const project of manifest.projects) {
      try {
        const result = await readArtifact(github, repo, artifacts.get(`mypyc-primer-result-${project.name}`), `${project.name}.json`, directory);
        validateResult(result, project, manifest);
        results.set(project.name, result);
      } catch (error) {
        core.warning(`${project.name}: ${error.message}`);
      }
    }
    const body = renderComment(manifest, results, logs, runUrl, run.conclusion);
    // Reading a large catalog can take time; recheck for new commits or retargeting.
    const { data: current } = await github.rest.pulls.get({ ...repo, pull_number: manifest.pr_number });
    if (current.state !== 'open' || current.head.sha !== manifest.head_sha ||
        (manifest.base_ref && current.base.ref !== manifest.base_ref)) return;
    await publish({ github, context }, manifest.pr_number, body);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

module.exports = { comment, publish, projectLogLinks, renderComment, fencedTail, validateManifest, validateResult };
