<script setup>
import { computed, ref } from 'vue'

const prompt = ref('Process the latest one candidate submission and show five roles for it.')
const conversation = ref([])
const conversationId = ref(crypto.randomUUID())
const latestResult = ref(null)
const isRunning = ref(false)

const UI_INJECTION_PATTERNS = [
  'ignore previous', 'ignore all previous', 'system prompt', 'developer message',
  'reveal instructions', 'jailbreak'
]

const workflowState = computed(() => {
  if (isRunning.value) return 'Processing request'
  if (!latestResult.value) return 'Ready for a request'
  if (latestResult.value.status === 'completed') return 'Completed for human review'
  if (latestResult.value.status === 'needs_clarification') return 'Needs clarification'
  return 'Workflow needs attention'
})

function useExample() {
  prompt.value = 'Process the latest five candidate submissions and show five roles for each.'
}

function startNewConversation() {
  conversation.value = []
  conversationId.value = crypto.randomUUID()
  latestResult.value = null
  prompt.value = 'Process the latest one candidate submission and show five roles for it.'
}

function uiGuardrailResponse(request) {
  const normalized = request.toLowerCase().replace(/\s+/g, ' ')
  if (UI_INJECTION_PATTERNS.some((pattern) => normalized.includes(pattern))) {
    return "I can’t change my workflow instructions or reveal internal configuration. I can help process candidate submissions, retrieve role suggestions, or explain the ESCO skills associated with a suggested role."
  }
  return null
}

function profileDetails(profile) {
  const details = []
  if (profile.declared_role) details.push(`Applied as ${profile.declared_role}`)
  if (profile.received_at) details.push(`Received ${profile.received_at}`)
  return details.join(' · ')
}

async function runWorkflow() {
  const request = prompt.value.trim()
  if (request.length < 3 || isRunning.value) return

  conversation.value.push({ id: crypto.randomUUID(), kind: 'recruiter', request })
  prompt.value = ''

  const blockedMessage = uiGuardrailResponse(request)
  if (blockedMessage) {
    conversation.value.push({
      id: crypto.randomUUID(),
      kind: 'assistant',
      result: {
        status: 'needs_clarification',
        response_type: 'guardrail',
        assistant_message: blockedMessage,
        gmail_connection_ok: null,
        validation_errors: [],
        formatted_results: []
      }
    })
    return
  }

  isRunning.value = true

  try {
    const response = await fetch('/api/run-workflow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: request, conversation_id: conversationId.value })
    })
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.detail || 'The workflow could not be started.')
    latestResult.value = payload
    conversation.value.push({ id: crypto.randomUUID(), kind: 'assistant', result: payload })
  } catch (requestError) {
    conversation.value.push({
      id: crypto.randomUUID(),
      kind: 'error',
      message: requestError.message || 'Could not reach the local workflow API.'
    })
  } finally {
    isRunning.value = false
  }
}
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <p class="eyebrow">LOCAL HUMAN-REVIEW DEMO</p>
        <h1>AI-Assisted Role Function</h1>
      </div>
      <div class="header-actions">
        <button class="text-button" type="button" @click="startNewConversation">New conversation</button>
        <div class="system-card">
          <p class="eyebrow">WORKFLOW STATUS</p>
          <strong>{{ workflowState }}</strong>
          <span class="status-dot" :class="{ active: latestResult?.status === 'completed' || isRunning }"></span>
        </div>
      </div>
    </header>

    <section class="conversation-panel" aria-label="Agent conversation">
      <div class="conversation-heading">
        <div>
          <p class="eyebrow teal">CONVERSATION</p>
          <h2>Candidate submission matching</h2>
        </div>
      </div>

      <div v-if="conversation.length === 0" class="conversation-empty">
        <div class="empty-icon">↗</div>
        <h3>Start a request</h3>
        <p>Ask the agent to process the candidate submissions from Gmail.</p>
      </div>

      <div v-else class="message-list">
        <template v-for="message in conversation" :key="message.id">
          <article v-if="message.kind === 'recruiter'" class="message recruiter-message">
            <p class="eyebrow">RECRUITER</p>
            <p>{{ message.request }}</p>
          </article>

          <article v-else-if="message.kind === 'error'" class="message error-message">
            <p class="eyebrow">WORKFLOW RESPONSE</p>
            <p>{{ message.message }}</p>
          </article>

          <article v-else class="message assistant-message">
            <header class="assistant-response-header">
              <div>
                <p class="eyebrow teal">AI-ASSISTED ROLE FUNCTION</p>
                <h3 v-if="message.result.response_type === 'guardrail'">Response</h3>
                <h3 v-else-if="message.result.response_type === 'gmail_connection_required'">Gmail connection required</h3>
                <h3 v-else-if="message.result.response_type === 'gmail_connection_unavailable'">Mailbox connection unavailable</h3>
                <h3 v-else-if="message.result.response_type === 'gmail_mailbox_unavailable'">Mailbox temporarily unavailable</h3>
                <h3 v-else-if="message.result.response_type === 'service_unavailable'">Service temporarily unavailable</h3>
                <h3 v-else-if="message.result.response_type === 'conversation_summary'">Conversation summary</h3>
                <h3 v-else-if="message.result.status === 'needs_clarification'">How can I help?</h3>
                <h3 v-else-if="message.result.response_type === 'follow_up'">Grounded follow-up</h3>
                <h3 v-else-if="message.result.assistant_message">No matching submissions</h3>
                <h3 v-else>{{ message.result.formatted_results?.length || 0 }} candidate{{ message.result.formatted_results?.length === 1 ? '' : 's' }} processed</h3>
              </div>
              <span v-if="message.result.response_type === 'gmail_connection_required'" class="connection-status neutral">
                <i></i> Secure connection needed
              </span>
              <span v-else-if="message.result.response_type === 'guardrail' || message.result.response_type === 'gmail_connection_unavailable' || message.result.response_type === 'conversation_summary' || message.result.status === 'needs_clarification'" class="connection-status neutral">
                <i></i> No tools were called
              </span>
              <span v-else :class="['connection-status', { okay: message.result.gmail_connection_ok }]">
                <i></i> Gmail {{ message.result.gmail_connection_ok ? 'connected' : 'unavailable' }}
              </span>
            </header>

            <p v-if="message.result.response_type === 'guardrail' || message.result.response_type === 'gmail_connection_required' || message.result.response_type === 'gmail_connection_unavailable'" class="assistant-message-text">
              {{ message.result.assistant_message }}
            </p>
            <p v-else-if="message.result.validation_errors?.length" :class="message.result.status === 'needs_clarification' ? 'clarification-message' : 'warning'">
              {{ message.result.validation_errors.join(' ') }}
            </p>

            <p v-if="message.result.assistant_message && message.result.response_type !== 'follow_up' && message.result.response_type !== 'guardrail'" class="assistant-message-text">
              {{ message.result.assistant_message }}
            </p>

            <section v-if="message.result.response_type === 'follow_up'" class="follow-up-response">
              <p>{{ message.result.assistant_message }}</p>
              <div class="follow-up-role">
                <span>Top suggested role</span>
                <strong>{{ message.result.follow_up.role_title }}</strong>
              </div>
              <div class="skill-list follow-up-skills">
                <span v-for="skill in message.result.follow_up.essential_skills" :key="skill">{{ skill }}</span>
              </div>
              <p class="evidence-note">{{ message.result.follow_up.evidence_note }}</p>
            </section>

            <article v-for="candidate in message.result.formatted_results" :key="candidate.candidate_submission.submission_id" class="candidate-card">
              <header v-if="Object.keys(candidate.candidate_profile).length" class="candidate-header">
                <div>
                  <p class="eyebrow">CANDIDATE PROFILE</p>
                  <h4 v-if="candidate.candidate_profile.display_name">{{ candidate.candidate_profile.display_name }}</h4>
                  <p v-if="profileDetails(candidate.candidate_profile)" class="timestamp">{{ profileDetails(candidate.candidate_profile) }}</p>
                </div>
                <span class="submission-id">{{ candidate.candidate_submission.submission_id.slice(-8) }}</span>
              </header>

              <div v-if="candidate.candidate_profile.attachment_count !== undefined" class="candidate-facts">
                <span>{{ candidate.candidate_profile.attachment_count }} supported attachment{{ candidate.candidate_profile.attachment_count === 1 ? '' : 's' }} processed</span>
              </div>

              <div class="role-list">
                <div v-for="role in candidate.role_suggestions" :key="role.rank" class="role-row">
                  <span class="rank">{{ String(role.rank).padStart(2, '0') }}</span>
                  <div class="role-copy">
                    <h5>{{ role.title }}</h5>
                    <p v-if="role.description">{{ role.description }}</p>
                    <div v-if="role.essential_skills?.length" class="skill-list">
                      <span v-for="skill in role.essential_skills" :key="skill">{{ skill }}</span>
                    </div>
                    <details v-if="role.semantic_similarity !== undefined" class="technical-details">
                      <summary>Programmatic details</summary>
                      <dl>
                        <div>
                          <dt>Retrieval method</dt>
                          <dd>Cosine similarity over local Nomic embeddings</dd>
                        </div>
                        <div>
                          <dt>Cosine similarity</dt>
                          <dd>{{ role.semantic_similarity.toFixed(4) }}</dd>
                        </div>
                      </dl>
                    </details>
                  </div>
                </div>
              </div>
              <footer>{{ candidate.human_review_note }}</footer>
            </article>
          </article>
        </template>
      </div>

      <div v-if="isRunning" class="thinking-message"><span class="spinner"></span> Processing the bounded workflow…</div>
    </section>

    <section class="composer">
      <div class="panel-heading">
        <div>
          <p class="eyebrow teal">REQUEST</p>
          <h3>What next?</h3>
        </div>
        <button class="text-button" type="button" @click="useExample">Use 5-candidate example</button>
      </div>
      <textarea v-model="prompt" :disabled="isRunning" aria-label="Recruiter request" placeholder="For example: Process the latest five candidate submissions and show five roles for each." />
      <div class="control-footer">
        <button class="primary-button" type="button" :disabled="isRunning || prompt.trim().length < 3" @click="runWorkflow">Send request</button>
      </div>
    </section>
  </main>
</template>
