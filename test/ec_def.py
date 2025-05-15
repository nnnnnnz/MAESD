# ec_def.py
from agents.system.tools.enzy_api import get_ec_info, validate_ec_number

def main():
    print("ExPASy EC 数据库查询工具")
    print("输入EC编号查询详细信息，输入q退出\n")

    while True:
        ec_input = input("请输入EC编号（如1.1.1.1 或 1.-.-.-或EC 1.1.1.1或ec 1.1.1.1）: ").strip()
        if ec_input.lower() == "q":
            break

        if not validate_ec_number(ec_input):
            print("EC编号格式错误！正确格式示例：1.1.1.1 或 1.-.-.-")
            continue

        info, error = get_ec_info(ec_input)

        if error:
            print(f"错误：{error}")
            continue
        print(info)

        print("\n=== 查询结果 ===")
        if 'definition' in info:
            print(f"EC分类: {info['ec_number']}")
            print(f"分类定义: {info['definition']}")
        else:
            print(f"EC编号: {info['ec_number']}")
            print(f"标准名称: {info['accepted_name']}")
            if info['alternative_names']:
                print(f"别名: {', '.join(info['alternative_names'])}")
            if info['reaction']:
                print("\n催化反应:")
                for r in info['reaction']:
                    print(f"  • {r}")
            if info['comments']:
                print("\n备注:")
                for c in info['comments']:
                    print(f"  › {c}")
        print("-"*40 + "\n")

if __name__ == "__main__":
    main()
