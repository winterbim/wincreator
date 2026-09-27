def resolve(defaults, file_cfg, env):
    result = dict(env)
    result.update(file_cfg)
    result.update(defaults)
    return result
