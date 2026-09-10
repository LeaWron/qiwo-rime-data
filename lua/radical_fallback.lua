-- 拆字模式兜底：没有候选时也把前缀留在编辑栏里
--
-- 部件拆字用 affix_segmentor 把前缀（u / uU）切成一个独立的 phony 段：
--   * 有候选时，radical_lookup/preedit_format 会把前缀拼回候选的 preedit，编辑栏正常；
--   * 没候选时（比如 unite 拆不出字），编辑栏只能回退到剥掉前缀后的原文，u 就「消失」了，
--     此时按空格提交的也是不带前缀的原文（nite）。
-- 这一点 librime 原生配置绕不开：phony 段的原文永远不计入 preedit 和提交文本；
-- matcher 又不独占本轮分段，撤掉 affix_segmentor 会让 abc 标签合并进同一段，拼音候选混进来。
-- 所以在拆字段的翻译结果为空时补一个「前缀 + 编码」的原文候选，preedit 与提交文本都带前缀，
-- 行为与拼音打不出字时显示原文一致。要放在 filters 列表最末：既看到的是最终结果，
-- 兜底候选也不会再被 autocap 之类的后续过滤器改写。
local M = {}

local TAG = "radical_lookup"

function M.init(env)
    local config = env.engine.schema.config
    env.prefix = config:get_string(TAG .. "/prefix") or ""
end

-- 只挂到拆字段上，拼音等其它段完全不经过本过滤器
function M.tags_match(seg, env)
    return seg:has_tag(TAG)
end

function M.func(input, env)
    local has_cand = false
    for cand in input:iter() do
        has_cand = true
        yield(cand)
    end
    if has_cand then
        return
    end

    local ctx = env.engine.context
    local comp = ctx.composition
    if comp:empty() then
        return
    end
    local seg = comp:back()
    if not seg:has_tag(TAG) then
        return
    end
    local code = ctx.input:sub(seg.start + 1, seg._end)
    if code == "" then
        return
    end

    local text = env.prefix .. code
    local cand = Candidate("raw", seg.start, seg._end, text, "")
    cand.preedit = text
    yield(cand)
end

return M
