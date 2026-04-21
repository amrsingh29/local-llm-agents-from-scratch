# Tool Schema Design

## What a Tool Schema Is

When you give an agent a tool, you give it two things:

1. **The function** — the actual Python code that runs when the tool is called
2. **The schema** — the description that tells the model what the tool does, how to call it, and what to expect back

In text-based ReAct, the schema is a line in the system prompt. In native tool calling, it is a structured JSON object. Either way, the model never sees the source code. It only sees the schema.

This means: **if the schema is wrong, the agent is broken — even if the code is perfect.**

---

## The Schema Is the Interface

Think of a tool schema the same way you think of a public API contract. The model is the client. Your function is the server. The schema is the documentation.

A junior developer cannot call an undocumented API correctly. A language model cannot call a poorly-described tool correctly.

The model uses the schema to decide:
- Whether this tool can solve the current sub-task
- What argument format to use
- What to expect in the response
- Whether the response indicates success or failure

Every ambiguity in the schema becomes a potential error in the agent's behaviour.

---

## The Four Elements of a Good Schema

### 1. Name — Unambiguous and Verb-Oriented

The tool name is how the model identifies what a tool does at a glance.

```
# Bad
- data_tool
- processor
- api_call

# Good
- search_web(query)
- calculate_tax(amount, rate)
- read_customer_record(customer_id)
```

Rule: the name alone should communicate the action. Vague nouns fail; specific verbs succeed.

### 2. Description — What It Does, What It Returns, When to Use It

The description must answer three questions the model will ask:
- What does this tool do?
- What does it return?
- When should I use it (vs other tools)?

```
# Bad
- calculator: does math

# Good
- calculator(expression) → evaluates a math expression using Python syntax and
  returns the result as a string. Use for any arithmetic, percentage, or formula
  calculation. Supports: +, -, *, /, (, ), decimal numbers.
  Example: calculator(100 * 1.08) → "108.0"
```

The good description tells the model:
- What the tool accepts (a math expression)
- What it returns (a string result)
- When to use it (arithmetic, percentage, formula)
- What syntax to use (Python syntax)
- What a real call looks like (the example)

### 3. Parameters — Typed and Constrained

Every parameter needs a type, a description, and ideally a range or example.

```
# Text-based ReAct (system prompt format)
- database_lookup(query) → queries the customer database and returns matching
  records as JSON. query: a plain-English description of what to find.
  Example: database_lookup(order status for customer 12345)

# Native tool calling (JSON schema format)
{
  "name": "database_lookup",
  "description": "Queries the customer database and returns matching records",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Plain-English description of what to find. Example: 'order status for customer 12345'"
      }
    },
    "required": ["query"]
  }
}
```

For native tool calling, the `required` field is critical. If a parameter is required but not listed, the model may omit it and the call will fail.

### 4. Error Semantics — What Failure Looks Like

If the tool can fail, the schema must say what failure looks like. Otherwise the model may interpret an error response as success.

```
# Bad (no error description)
- stock_api(ticker) → returns current stock price

# Good
- stock_api(ticker) → returns current stock price as a number string.
  Returns a JSON object with status 503 if the service is unavailable.
  If you receive a 503, wait and retry or inform the user the service is down.
  Example success: "226.50"
  Example failure: {"status": 503, "retry_after": 30}
```

Without the error description, the model sees `{"status": 503}` and does not know whether to retry, use a fallback, or report failure.

---

## The Three Tool Design Mistakes

### Mistake 1: Overloaded Tools

A tool that does too many things forces the model to guess which behaviour applies.

```
# Bad — one tool doing three things
- data_tool(action, target) → if action is "read", reads a file.
  If action is "search", queries the database. If action is "calculate", does math.

# Good — three focused tools
- file_read(path) → reads a file
- database_search(query) → queries the database
- calculator(expression) → evaluates a math expression
```

Focused tools are easier for the model to select correctly. An overloaded tool requires the model to understand a mini-language — and it will sometimes get it wrong.

### Mistake 2: Ambiguous Return Values

When the return value is not described, the model interprets it however it likes.

```python
# Tool returns this
{"found": True, "data": {"price": 49.99, "currency": "USD"}}

# Schema says only
- product_lookup(id) → looks up a product

# Model may interpret the return as:
"The product was found at $49.99."  # correct
"The product lookup succeeded."  # vague, loses the price
"true"  # misreads the boolean
```

Always describe what the returned data structure looks like and which fields matter.

### Mistake 3: Missing the Negative Cases

Tools that can fail without raising an exception — returning 404, empty results, null values — must have those cases documented.

```
# Missing negative case
- user_lookup(email) → returns user profile

# Complete
- user_lookup(email) → returns user profile as JSON if found.
  Returns {"error": "not found"} if no user exists with that email.
  Never raises an exception.
```

If the model has never been told what "not found" looks like, it may treat an error response as a valid profile and hallucinate the missing fields.

---

## Schemas in Native Tool Calling

When using Ollama's native tool calling (for models that support it), schemas are passed as structured JSON in the API payload rather than as text in the system prompt:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluates a math expression and returns the result as a string. Supports +, -, *, /, (, ), decimal numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate. Example: 84.50 * 0.15"
                    }
                },
                "required": ["expression"]
            }
        }
    }
]

payload = {
    "model": "gemma4:26b",
    "messages": messages,
    "tools": tools,
}
```

The model returns a structured tool call rather than a text `Action:` line:

```json
{
  "message": {
    "role": "assistant",
    "tool_calls": [{
      "function": {
        "name": "calculator",
        "arguments": {"expression": "84.50 * 0.15"}
      }
    }]
  }
}
```

The schema quality still matters — the model still chooses which tool to call and what arguments to use based on the description. A bad description produces bad tool calls even in native mode.

---

## Practical Schema Checklist

Before registering a tool in your agent:

- [ ] Name is a verb that describes the action
- [ ] Description says what it does, what it returns, and when to use it
- [ ] Every parameter has a type and a description
- [ ] At least one concrete call example is included
- [ ] Error responses are described (what does failure look like?)
- [ ] If multiple tools exist, descriptions distinguish when to use each one

---

## The Schema Governs Agent Quality

You can have the most capable model in the world and perfectly implemented tools. If the schemas are vague, the agent will:
- Pick the wrong tool for a task
- Pass the wrong argument format
- Misinterpret error responses as success
- Hallucinate the meaning of ambiguous return values

Schema design is not documentation work — it is agent architecture. Treat it as carefully as you treat the tool implementation itself.

---

## Enterprise Implication

In production agent systems, tool schemas become part of the API contract between:
- The AI team (who writes the agent)
- The backend team (who implements the tools)
- The platform team (who maintains the model)

Schema versioning matters. If a tool's return format changes without updating the schema, every agent that calls that tool will misinterpret the new response. This is not a model bug — it is a schema drift bug. The same class of problem that breaks REST API clients when server responses change undocumented.

In regulated environments (finance, healthcare), tool schemas must also document:
- What data the tool can access
- Whether the tool has side effects (read-only vs write)
- Maximum allowed call frequency
- What audit log entries the tool generates

A tool schema is not just "how to call this function." It is the model's view of what the system can do. Design it accordingly.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Tool schema | The description of a tool given to the model — name, parameters, return value, error semantics |
| Schema drift | When the tool's actual behaviour changes but the schema is not updated |
| Native tool calling | Structured JSON tool schema format supported by the model API |
| Required parameters | Parameters the model must always include; if missing, the call fails |
| Error semantics | Documentation of what failure looks like in the tool's return value |

---

## Phase 3 Complete

The five Phase 3 concepts are:
1. **What is an agent vs a pipeline** — dynamic decision-making vs fixed steps
2. **The agent loop** — Perceive → Think → Act → Observe, and how it terminates
3. **ReAct from first principles** — the text format that makes tool calling parseable
4. **Tool calling internals and error handling** — the four failure modes, stop sequences, hallucination risk
5. **Tool schema design** — why the description is as important as the implementation

**Next:** Phase 4 — Edge AI and On-Device Intelligence. Running Gemma 4 E2B alongside 26B, building a benchmark harness, and creating the decision framework for when to use a local model vs an API model.
